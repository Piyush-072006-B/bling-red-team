"""
Knowledge Base Store — Append-Only Evasion Knowledge Base
==========================================================
Writes evasion findings to evasion_kb (in-memory in v1; Postgres in Phase 3).
Never updates or deletes rows — append-only invariant.

WARNING: in-memory only. Single-process. Data lost on restart.
Persistence via Postgres/Redis is deferred to post-hackathon.

Severity scoring:
  CRITICAL — evasion_success=True AND gate_bypassed AND context_multiplier_abused
  HIGH     — evasion_success=True AND gate_bypassed
  MEDIUM   — score dropped below REVIEW threshold (0.50) from HIGH_RISK (>=0.75)
  LOW      — score reduced but still above 0.50

Public API:
    append_evasion(evasion_data: dict) -> str   # returns row UUID
    query_evasions(filters)          -> list[dict]
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.core.utils.audit_logger import get_logger

log = get_logger(__name__)

# Score thresholds (must match Blue Team / evaluators.py)
_HIGH_RISK_THRESHOLD = 0.75
_REVIEW_THRESHOLD = 0.50

# In-memory store (replaced by Postgres in Phase 3 via SQLAlchemy async session)
_evasion_kb: list[dict[str, Any]] = []


# ─────────────────────────────────────────────────────────────────────────────
# Severity scoring
# ─────────────────────────────────────────────────────────────────────────────


def _compute_severity(
    evasion_success: bool,
    gate_bypassed: str | None,
    context_multiplier_abused: str | None,
    score_original: float | None,
    score_mutated: float | None,
) -> str:
    """
    Compute evasion severity based on the outcome.

    CRITICAL — evasion_success AND gate bypassed AND context multiplier abused
    HIGH     — evasion_success AND gate bypassed
    MEDIUM   — score dropped from HIGH_RISK (>=0.75) to below REVIEW (0.50)
    LOW      — any score reduction (but still >= 0.50 or evasion not confirmed)
    """
    if evasion_success and gate_bypassed and context_multiplier_abused:
        return "CRITICAL"

    if evasion_success and gate_bypassed:
        return "HIGH"

    if (
        score_original is not None
        and score_mutated is not None
        and score_original >= _HIGH_RISK_THRESHOLD
        and score_mutated < _REVIEW_THRESHOLD
    ):
        return "MEDIUM"

    return "LOW"


# ─────────────────────────────────────────────────────────────────────────────
# Append-only write
# ─────────────────────────────────────────────────────────────────────────────


def append_evasion(evasion_data: dict[str, Any]) -> str:
    """
    Append a new evasion record to the knowledge base.
    Computes severity automatically if not provided.
    Never updates or deletes existing rows.

    Args:
        evasion_data: Dict with fields:
            archetype               str   — confirmed archetype or NEW_VARIANT
            evasion_vector          dict  — the mutated feature vector
            gate_bypassed           list[str] | None  — gates that were bypassed
            feature_deltas          dict  — delta between original and mutated vector
            context_multiplier_abused  str | None
            evasion_success         bool
            score_original          float | None
            score_mutated           float | None
            ingest_log_id           str | None
            mutation_type           str | None
            gate_probe_result       dict | None
            feature_sensitivity_result dict | None
            context_bypass_result   dict | None

    Returns:
        str — UUID of the new row
    """
    row_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    # ── Extract and normalise fields ────────────────────────────────
    archetype: str = evasion_data.get("archetype", "UNKNOWN")
    evasion_vector: dict = evasion_data.get("evasion_vector", {})
    gate_bypassed_raw = evasion_data.get("gate_bypassed")
    if isinstance(gate_bypassed_raw, str):
        gate_bypassed_list = [gate_bypassed_raw] if gate_bypassed_raw else []
    elif isinstance(gate_bypassed_raw, list):
        gate_bypassed_list = gate_bypassed_raw
    else:
        gate_bypassed_list = []

    feature_deltas: dict = evasion_data.get("feature_deltas", {})
    context_multiplier_abused: str | None = evasion_data.get("context_multiplier_abused")
    evasion_success: bool = bool(evasion_data.get("evasion_success", False))
    score_original: float | None = evasion_data.get("score_original")
    score_mutated: float | None = evasion_data.get("score_mutated")

    # ── Compute severity ────────────────────────────────────────────
    provided_severity = evasion_data.get("severity")
    if provided_severity and provided_severity in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
        severity = provided_severity
    else:
        severity = _compute_severity(
            evasion_success=evasion_success,
            gate_bypassed=gate_bypassed_list[0] if gate_bypassed_list else None,
            context_multiplier_abused=context_multiplier_abused,
            score_original=score_original,
            score_mutated=score_mutated,
        )

    # ── Build row ──────────────────────────────────────────────────
    row: dict[str, Any] = {
        "id": row_id,
        "archetype": archetype,
        "evasion_vector": evasion_vector,
        "gate_bypassed": gate_bypassed_list,
        "feature_deltas": feature_deltas,
        "context_multiplier_abused": context_multiplier_abused,
        "severity": severity,
        "evasion_success": evasion_success,
        "score_original": score_original,
        "score_mutated": score_mutated,
        "ingest_log_id": evasion_data.get("ingest_log_id"),
        "mutation_type": evasion_data.get("mutation_type"),
        "gate_probe_result": evasion_data.get("gate_probe_result"),
        "feature_sensitivity_result": evasion_data.get("feature_sensitivity_result"),
        "context_bypass_result": evasion_data.get("context_bypass_result"),
        "tgep_threat_level": evasion_data.get("tgep_threat_level"),
        "tgep_patterns_detected": evasion_data.get("tgep_patterns_detected"),
        "tgep_recommended_patch": evasion_data.get("tgep_recommended_patch"),
        "tgep_response": evasion_data.get("tgep_response"),
        "tgep_graph": evasion_data.get("tgep_graph"),
        "created_at": now,
    }

    # APPEND ONLY — never modify existing rows
    _evasion_kb.append(row)

    log.info(
        "evasion_kb_appended",
        row_id=row_id,
        archetype=archetype,
        severity=severity,
        evasion_success=evasion_success,
        gate_bypassed=gate_bypassed_list,
    )
    return row_id


# ─────────────────────────────────────────────────────────────────────────────
# Query
# ─────────────────────────────────────────────────────────────────────────────


def update_evasion_tgep_result(row_id: str, tgep_result: dict[str, Any]) -> None:
    """Update an existing evasion record with TGEP evaluation results and raw response."""
    row = get_evasion_by_id(row_id)
    if row:
        row["tgep_threat_level"] = tgep_result.get("threat_level")
        row["tgep_patterns_detected"] = tgep_result.get("patterns_detected")
        row["tgep_recommended_patch"] = tgep_result.get("recommended_patch")
        row["tgep_response"] = tgep_result


def query_evasions(
    severity: str | None = None,
    archetype: str | None = None,
    gate: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """
    Query the evasion knowledge base with optional filters.

    Args:
        severity:  Filter by severity (LOW | MEDIUM | HIGH | CRITICAL)
        archetype: Filter by archetype name
        gate:      Filter to rows where this gate appears in gate_bypassed list
        limit:     Max rows to return (default 20)
        offset:    Rows to skip (for pagination)

    Returns:
        List of matching evasion_kb rows (most recent first).
    """
    results = list(reversed(_evasion_kb))  # most recent first

    if severity:
        results = [r for r in results if r["severity"] == severity.upper()]

    if archetype:
        results = [r for r in results if r["archetype"] == archetype]

    if gate:
        results = [r for r in results if gate in (r.get("gate_bypassed") or [])]

    return results[offset : offset + limit]


def get_evasion_by_id(row_id: str) -> dict[str, Any] | None:
    """Return a single evasion_kb row by UUID, or None if not found."""
    for row in _evasion_kb:
        if row["id"] == row_id:
            return row
    return None


def get_all_evasions() -> list[dict[str, Any]]:
    """Return all evasion_kb rows. Used in tests."""
    return list(_evasion_kb)


def reset_kb() -> None:
    """Clear the knowledge base. Used in tests only."""
    _evasion_kb.clear()
