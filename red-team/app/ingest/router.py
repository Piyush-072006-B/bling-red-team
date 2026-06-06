"""
Ingest Router — Triage, Dedup, Priority Queue
===============================================
Handles incoming Red Team signals:
  1. Deduplicate by transaction_id hash (check ingest_log first)
  2. Assign priority: FRAUD_DNA=HIGH, NOVELTY w/ occurrence_count>=15=CRITICAL,
     NOVELTY w/ occurrence_count<15=HIGH, GATE_MISS=MEDIUM
  3. Write sanitized record to ingest_log (PII fields are hashed, never stored raw)
  4. Push to in-process asyncio.Queue for analysis pipeline

Returns: {"ingest_id": str, "priority": str, "queued_for": str}

WARNING: in-memory only. Single-process. Data lost on restart.
Persistence via Postgres/Redis is deferred to post-hackathon.

Note: asyncio.Queue is used in v1. Celery replaces it in Phase 3.
"""

from __future__ import annotations

import asyncio
import hashlib
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from app.config import get_settings
from app.utils.audit_logger import get_logger, hash_id

if TYPE_CHECKING:
    from app.ingest.schemas import FraudDNA, GateMissLog, IngestPayload, NoveltyEscalation

log = get_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# In-process analysis queues (one per priority tier)
# Replace with Celery queues in Phase 3.
# ─────────────────────────────────────────────────────────────────────────────

# WARNING: in-memory only. Single-process. Data lost on restart.
# Persistence via Postgres/Redis is deferred to post-hackathon.
#
# Queue sizes are bounded by INGEST_QUEUE_MAX_SIZE (default 1000 per tier).
# When a put_nowait() fails, ingest_signal raises QueueFullError -> HTTP 503.
_queues: dict[str, asyncio.Queue] = {
    "CRITICAL": asyncio.Queue(maxsize=get_settings().ingest_queue_max_size),
    "HIGH":     asyncio.Queue(maxsize=get_settings().ingest_queue_max_size),
    "MEDIUM":   asyncio.Queue(maxsize=get_settings().ingest_queue_max_size),
    "LOW":      asyncio.Queue(maxsize=get_settings().ingest_queue_max_size),
}

# In-memory dedup set (replaced by DB check when DB is available)
# Maps transaction_id_hash → ingest_id
_seen_hashes: dict[str, str] = {}

# In-memory ingest log (replaced by DB write when DB is available)
_ingest_log: list[dict[str, Any]] = []


# ─────────────────────────────────────────────────────────────────────────────
# Priority assignment
# ─────────────────────────────────────────────────────────────────────────────


def _assign_priority(payload: "IngestPayload") -> str:
    """Return priority string for the given payload type."""
    source = payload.source_type

    if source == "FRAUD_DNA":
        return "HIGH"

    if source == "NOVELTY":
        # Import here to avoid circular; type is resolved at runtime
        from app.ingest.schemas import NoveltyEscalation

        if isinstance(payload, NoveltyEscalation) and payload.occurrence_count >= 15:
            return "CRITICAL"
        return "HIGH"

    if source == "GATE_MISS":
        return "MEDIUM"

    return "LOW"


def _queued_for_label(source_type: str, priority: str) -> str:
    """Human-readable label for which analysis pipeline this signal is queued for."""
    labels = {
        "FRAUD_DNA": "archetype_extraction + mutation_engine",
        "NOVELTY": "archetype_extraction + graph_adversary",
        "GATE_MISS": "graph_adversary",
    }
    return labels.get(source_type, "general_analysis")


# ─────────────────────────────────────────────────────────────────────────────
# Dedup helpers
# ─────────────────────────────────────────────────────────────────────────────


def _make_dedup_hash(payload: "IngestPayload") -> str | None:
    """
    Return a deterministic hash for deduplication.
    Uses transaction_id for FRAUD_DNA and GATE_MISS.
    Uses fingerprint_id for NOVELTY.
    Returns None if no dedup key is available.
    """
    settings = get_settings()
    salt = settings.pii_hash_salt

    if payload.source_type == "FRAUD_DNA":
        raw = payload.transaction_id  # type: ignore[union-attr]
    elif payload.source_type == "GATE_MISS":
        raw = payload.transaction_id  # type: ignore[union-attr]
    elif payload.source_type == "NOVELTY":
        raw = payload.fingerprint_id  # type: ignore[union-attr]
    else:
        return None

    return hashlib.sha256(f"{salt}{raw}".encode()).hexdigest()


# ─────────────────────────────────────────────────────────────────────────────
# Main ingest function
# ─────────────────────────────────────────────────────────────────────────────


class DuplicateIngestError(Exception):
    """Raised when a payload with the same dedup key has already been ingested."""

    def __init__(self, existing_ingest_id: str) -> None:
        self.existing_ingest_id = existing_ingest_id
        super().__init__(f"Duplicate signal — already ingested as {existing_ingest_id}")


class QueueFullError(Exception):
    """Raised when all priority queues are at capacity (HTTP 503)."""


def _sanitize_payload(payload: "IngestPayload") -> dict:
    """
    Return a sanitized copy of the payload dict with PII fields replaced by
    sha256(SALT+value)[:12] hashes. Raw account_id, transaction_id,
    fingerprint_id, and alert_id are NEVER stored in the ingest_log.
    """
    settings = get_settings()
    salt = settings.pii_hash_salt
    data = payload.model_dump(mode="json")

    def _h(value: str | None) -> str | None:
        if value is None:
            return None
        return hashlib.sha256(f"{salt}{value}".encode()).hexdigest()[:12]

    for field in ("account_id", "transaction_id", "fingerprint_id", "alert_id"):
        if field in data and data[field] is not None:
            data[field] = _h(str(data[field]))
    return data


async def ingest_signal(payload: "IngestPayload") -> dict[str, str]:
    """
    Triage, dedup, and queue a Red Team ingest signal.

    Args:
        payload: Validated FraudDNA | NoveltyEscalation | GateMissLog

    Returns:
        {"ingest_id": str, "priority": str, "queued_for": str}

    Raises:
        DuplicateIngestError: if the same signal was already ingested.
        QueueFullError: if the priority queue is at capacity.
    """
    ingest_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    priority = _assign_priority(payload)
    queued_for = _queued_for_label(payload.source_type, priority)

    # ── 1. Dedup ────────────────────────────────────────────────────────
    dedup_hash = _make_dedup_hash(payload)
    if dedup_hash and dedup_hash in _seen_hashes:
        existing_id = _seen_hashes[dedup_hash]
        log.info(
            "ingest_duplicate",
            source_type=payload.source_type,
            dedup_hash=dedup_hash[:8],
            existing_ingest_id=existing_id,
        )
        raise DuplicateIngestError(existing_ingest_id=existing_id)

    # ── 2. Record sanitized ingest log (PII fields are hashed) ──────────
    sanitized = _sanitize_payload(payload)
    log_entry: dict[str, Any] = {
        "id": ingest_id,
        "source_type": payload.source_type,
        "raw_payload": sanitized,
        "received_at": now.isoformat(),
        "status": "QUEUED",
        "priority": priority,
        "transaction_id_hash": dedup_hash,
    }
    _ingest_log.append(log_entry)

    # ── 3. Register dedup hash ──────────────────────────────────────────
    if dedup_hash:
        _seen_hashes[dedup_hash] = ingest_id

    # ── 4. Push to priority queue (non-blocking; 503 if full) ───────────
    queue_item = {
        "ingest_id": ingest_id,
        "priority": priority,
        "source_type": payload.source_type,
        "payload": payload,
        "enqueued_at": now.isoformat(),
    }
    try:
        _queues[priority].put_nowait(queue_item)
    except asyncio.QueueFull:
        # Roll back the log entry and dedup hash so the caller can retry cleanly
        _ingest_log.remove(log_entry)
        if dedup_hash:
            _seen_hashes.pop(dedup_hash, None)
        raise QueueFullError()

    # ── 5. Structured log (no PII) ──────────────────────────────────────
    log_kwargs: dict[str, Any] = {
        "ingest_id": ingest_id,
        "source_type": payload.source_type,
        "priority": priority,
        "queued_for": queued_for,
    }
    # Log hashed IDs only — never raw PII
    if hasattr(payload, "account_id"):
        log_kwargs["account_hash"] = hash_id(payload.account_id)  # type: ignore[union-attr]
    if hasattr(payload, "transaction_id"):
        log_kwargs["txn_hash"] = dedup_hash[:8] if dedup_hash else "n/a"

    log.info("ingest_accepted", **log_kwargs)

    return {
        "ingest_id": ingest_id,
        "priority": priority,
        "queued_for": queued_for,
    }


def get_queue(priority: str) -> asyncio.Queue:
    """Return the asyncio.Queue for the given priority tier."""
    return _queues[priority]


def get_ingest_log() -> list[dict[str, Any]]:
    """Return the in-memory ingest log (all entries). Used by tests and report endpoint."""
    return _ingest_log


def get_seen_hashes() -> dict[str, str]:
    """Return the dedup hash map. Used by tests."""
    return _seen_hashes


def reset_state() -> None:
    """
    Clear all in-memory state. Used in tests only.
    Never call in production.
    """
    _ingest_log.clear()
    _seen_hashes.clear()
    for q in _queues.values():
        while not q.empty():
            try:
                q.get_nowait()
            except asyncio.QueueEmpty:
                break


def update_ingest_status(
    ingest_id: str,
    status: str,
    error: str | None = None,
) -> bool:
    """
    Update the status field (and optional error field) of an ingest_log entry.
    Returns True if the entry was found and updated, False otherwise.
    Valid statuses: QUEUED | IN_PROGRESS | COMPLETED | FAILED
    """
    for entry in _ingest_log:
        if entry["id"] == ingest_id:
            entry["status"] = status
            if error is not None:
                entry["error"] = error
            log.info(
                "ingest_status_updated",
                ingest_id=ingest_id,
                status=status,
                has_error=error is not None,
            )
            return True
    log.warning("ingest_status_update_not_found", ingest_id=ingest_id, status=status)
    return False

