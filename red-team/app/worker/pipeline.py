"""
Background Worker Pipeline — asyncio.Task-Based Queue Consumer
==============================================================
Consumes ingested payloads from the priority queues and orchestrates
the full Red Team analysis pipeline:

  FRAUD_DNA  → archetype_extractor → mutation_engine
                → shadow_scorer (per mutation) → evaluators
                → kb_store.append_evasion (per mutation)
                → maybe_fire_tgep_for_report

  NOVELTY    → archetype_extractor (using structural_features)
                → graph_adversary.generate_all_bypasses
                → kb_store.append_evasion (per bypass)

  GATE_MISS  → graph_adversary.generate_bypass (for the specific gate)
                → kb_store.append_evasion

On failure: the ingest_log entry is marked FAILED with an error field.
No retries are performed.

Start with:
    asyncio.create_task(worker_loop())
inside the FastAPI lifespan context.
"""

from __future__ import annotations

import asyncio
import traceback
from typing import Any

from app.engines.archetype_extractor import extract_archetype
from app.engines.graph_adversary import VALID_GATES, generate_all_bypasses, generate_bypass
from app.engines.mutation_engine import generate_mutations
from app.ingest.router import _queues, get_ingest_log, update_ingest_status
from app.knowledge.kb_store import append_evasion
from app.sandbox.evaluators import context_bypass, feature_sensitivity, gate_probe
from app.sandbox.shadow_scorer import score_transaction
from app.api.tgep_webhook import maybe_fire_tgep_for_report
from app.utils.audit_logger import get_logger

log = get_logger(__name__)

# Priority order — CRITICAL is drained first
_PRIORITY_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]

# Sentinel score returned when shadow scorer is unavailable
_UNAVAILABLE_SCORE: dict[str, Any] = {
    "score": None,
    "action": None,
    "gate_fired": None,
    "error": "shadow_scorer_unavailable",
}


# ─────────────────────────────────────────────────────────────────────────────
# Main loop
# ─────────────────────────────────────────────────────────────────────────────


async def worker_loop() -> None:
    """
    Infinite worker loop.  Runs as a background asyncio.Task.
    Polls queues in priority order (CRITICAL → HIGH → MEDIUM → LOW).
    On cancellation (app shutdown), exits cleanly.
    """
    log.info("worker_loop_started")
    while True:
        try:
            item = await _dequeue_next()
            await _process_item(item)
        except asyncio.CancelledError:
            log.info("worker_loop_cancelled")
            break
        except Exception as exc:
            # Unexpected top-level error — log and continue
            log.error(
                "worker_loop_unexpected_error",
                error=str(exc),
                traceback=traceback.format_exc(),
            )
            await asyncio.sleep(0.1)


# ─────────────────────────────────────────────────────────────────────────────
# Queue drain helper
# ─────────────────────────────────────────────────────────────────────────────


async def _dequeue_next() -> dict[str, Any]:
    """
    Wait until an item is available in any queue, honouring priority order.
    Uses asyncio.wait with a 0-timeout peek on each queue before blocking
    on the CRITICAL queue to avoid busy-polling on empty high-priority queues.
    """
    while True:
        # Try each queue in priority order (non-blocking)
        for priority in _PRIORITY_ORDER:
            q = _queues[priority]
            try:
                return q.get_nowait()
            except asyncio.QueueEmpty:
                continue
        # All queues empty — block on CRITICAL until something arrives,
        # then re-check all queues so we respect priority ordering.
        # We use asyncio.wait_for with a short timeout so high-priority items
        # that arrive while blocking on LOW aren't starved.
        try:
            item = await asyncio.wait_for(_queues["CRITICAL"].get(), timeout=0.05)
            return item
        except asyncio.TimeoutError:
            # Give control back to the event loop briefly
            await asyncio.sleep(0.01)


# ─────────────────────────────────────────────────────────────────────────────
# Dispatcher
# ─────────────────────────────────────────────────────────────────────────────


async def _process_item(item: dict[str, Any]) -> None:
    """Route a queue item to the correct pipeline based on source_type."""
    ingest_id: str = item["ingest_id"]
    source_type: str = item["source_type"]
    payload = item["payload"]

    log.info(
        "worker_processing",
        ingest_id=ingest_id,
        source_type=source_type,
        priority=item.get("priority"),
    )
    update_ingest_status(ingest_id, "IN_PROGRESS")

    try:
        if source_type == "FRAUD_DNA":
            await _pipeline_fraud_dna(ingest_id, payload)
        elif source_type == "NOVELTY":
            await _pipeline_novelty(ingest_id, payload)
        elif source_type == "GATE_MISS":
            await _pipeline_gate_miss(ingest_id, payload)
        else:
            log.warning("worker_unknown_source_type", source_type=source_type)

        update_ingest_status(ingest_id, "COMPLETED")
        log.info("worker_item_completed", ingest_id=ingest_id, source_type=source_type)

    except Exception as exc:
        update_ingest_status(ingest_id, "FAILED", error=str(exc))
        log.error(
            "worker_item_failed",
            ingest_id=ingest_id,
            source_type=source_type,
            error=str(exc),
            traceback=traceback.format_exc(),
        )


# ─────────────────────────────────────────────────────────────────────────────
# FRAUD_DNA pipeline
# ─────────────────────────────────────────────────────────────────────────────


async def _pipeline_fraud_dna(ingest_id: str, payload: Any) -> None:
    """
    Full pipeline for FRAUD_DNA signals:
      1. Extract archetype from feature_vector
      2. Generate 10 mutations
      3. For each mutation:
         a. Score original vector via shadow scorer
         b. Score mutated vector via shadow scorer
         c. Run gate_probe, feature_sensitivity, context_bypass evaluators
         d. Append evasion record to KB
      4. Fire TGEP webhook if any HIGH/CRITICAL evasions found
    """
    feature_vector: dict[str, float] = payload.feature_vector

    # Step 1 — Archetype extraction
    archetype_result = extract_archetype(feature_vector)
    archetype: str = archetype_result["archetype"]  # type: ignore[assignment]

    # Step 2 — Score original vector
    original_score_result = await score_transaction(
        feature_vector,
        metadata={"ingest_id": ingest_id, "archetype": archetype},
    )

    # Step 3 — Generate mutations
    mutations = generate_mutations(feature_vector, archetype, n=10)

    evasion_ids: list[str] = []

    for mutation in mutations:
        mutated_vector: dict[str, float] = mutation["mutated_vector"]

        # Score mutated vector
        mutated_score_result = await score_transaction(
            mutated_vector,
            metadata={
                "ingest_id": ingest_id,
                "mutation_id": mutation["mutation_id"],
                "mutation_type": mutation["mutation_type"],
            },
        )

        # Run evaluators
        gp = gate_probe(original_score_result, mutated_score_result, mutation)
        fs = feature_sensitivity(original_score_result, mutated_score_result, mutation)
        cb = context_bypass(original_score_result, mutated_score_result, mutation)

        # Build evasion record
        evasion_data: dict[str, Any] = {
            "archetype": archetype,
            "evasion_vector": mutated_vector,
            "gate_bypassed": gp.get("gate_bypassed"),
            "feature_deltas": mutation.get("delta_features", {}),
            "context_multiplier_abused": cb.get("multiplier_abused"),
            "evasion_success": gp.get("evasion_achieved", False),
            "score_original": gp.get("original_score"),
            "score_mutated": gp.get("mutated_score"),
            "ingest_log_id": ingest_id,
            "mutation_type": mutation.get("mutation_type"),
            "gate_probe_result": gp,
            "feature_sensitivity_result": fs,
            "context_bypass_result": cb,
        }
        evasion_id = append_evasion(evasion_data)
        evasion_ids.append(evasion_id)

    # Fire TGEP webhook — only fires for HIGH/CRITICAL + recommended_action=PATCH
    report = _build_report_for_tgep(ingest_id, archetype, evasion_ids)
    await maybe_fire_tgep_for_report(report)


# ─────────────────────────────────────────────────────────────────────────────
# NOVELTY pipeline
# ─────────────────────────────────────────────────────────────────────────────


async def _pipeline_novelty(ingest_id: str, payload: Any) -> None:
    """
    Pipeline for NOVELTY escalation signals:
      1. Extract archetype from structural_features
      2. Generate all 5 gate bypasses (structural novelty warrants full adversarial run)
      3. Append each bypass as an evasion record to the KB
    """
    structural_features: dict[str, float] = payload.structural_features

    # Extract archetype from structural features
    archetype_result = extract_archetype(structural_features)
    archetype: str = archetype_result["archetype"]  # type: ignore[assignment]

    # Generate all 5 gate bypasses
    transaction_data = {"amount": structural_features.get("amount_series_score", 50000.0) * 100000}
    bypasses = generate_all_bypasses(transaction_data)

    for bypass in bypasses:
        gate_name: str = bypass["gate_name"]
        evasion_data: dict[str, Any] = {
            "archetype": archetype,
            "evasion_vector": structural_features,
            "gate_bypassed": [gate_name],
            "feature_deltas": {},
            "context_multiplier_abused": None,
            "evasion_success": True,  # bypass is designed to avoid the gate
            "score_original": None,
            "score_mutated": None,
            "ingest_log_id": ingest_id,
            "mutation_type": f"graph_bypass_{gate_name}",
            "gate_probe_result": {
                "bypass_strategy": bypass.get("bypass_strategy"),
                "synthetic_subgraph_summary": {
                    "nodes": len(bypass.get("synthetic_subgraph", {}).get("nodes", [])),
                    "edges": len(bypass.get("synthetic_subgraph", {}).get("edges", [])),
                },
                "expected_to_trigger": bypass.get("expected_to_trigger"),
            },
            "feature_sensitivity_result": None,
            "context_bypass_result": None,
        }
        append_evasion(evasion_data)

    log.info(
        "novelty_pipeline_complete",
        ingest_id=ingest_id,
        archetype=archetype,
        bypasses_generated=len(bypasses),
    )


# ─────────────────────────────────────────────────────────────────────────────
# GATE_MISS pipeline
# ─────────────────────────────────────────────────────────────────────────────


async def _pipeline_gate_miss(ingest_id: str, payload: Any) -> None:
    """
    Pipeline for GATE_MISS signals:
      1. Generate a bypass for the specific gate that was missed
      2. Append the bypass as an evasion record to the KB
    """
    gate_name: str = payload.gate_name
    transaction_id: str = payload.transaction_id

    # Normalise gate name (payload may use underscores, VALID_GATES uses underscores too)
    normalised_gate = gate_name.lower().replace("-", "_")
    if normalised_gate not in VALID_GATES:
        log.warning(
            "gate_miss_unknown_gate",
            gate_name=gate_name,
            ingest_id=ingest_id,
            valid_gates=sorted(VALID_GATES),
        )
        # Still record the miss but without a bypass
        append_evasion({
            "archetype": "UNKNOWN",
            "evasion_vector": {},
            "gate_bypassed": [gate_name],
            "feature_deltas": {},
            "context_multiplier_abused": None,
            "evasion_success": False,
            "score_original": None,
            "score_mutated": None,
            "ingest_log_id": ingest_id,
            "mutation_type": f"gate_miss_{gate_name}",
            "gate_probe_result": None,
            "feature_sensitivity_result": None,
            "context_bypass_result": None,
        })
        return

    bypass = generate_bypass(normalised_gate, {"amount": 50000.0})

    evasion_data: dict[str, Any] = {
        "archetype": "UNKNOWN",
        "evasion_vector": {},
        "gate_bypassed": [normalised_gate],
        "feature_deltas": {},
        "context_multiplier_abused": None,
        "evasion_success": True,
        "score_original": None,
        "score_mutated": None,
        "ingest_log_id": ingest_id,
        "mutation_type": f"graph_bypass_{normalised_gate}",
        "gate_probe_result": {
            "bypass_strategy": bypass.get("bypass_strategy"),
            "synthetic_subgraph_summary": {
                "nodes": len(bypass.get("synthetic_subgraph", {}).get("nodes", [])),
                "edges": len(bypass.get("synthetic_subgraph", {}).get("edges", [])),
            },
            "expected_to_trigger": bypass.get("expected_to_trigger"),
        },
        "feature_sensitivity_result": None,
        "context_bypass_result": None,
    }
    append_evasion(evasion_data)

    log.info(
        "gate_miss_pipeline_complete",
        ingest_id=ingest_id,
        gate_name=normalised_gate,
        transaction_id=transaction_id,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _build_report_for_tgep(
    ingest_id: str,
    archetype: str,
    evasion_ids: list[str],
) -> dict[str, Any]:
    """
    Build a properly-shaped report dict that satisfies maybe_fire_tgep_for_report's
    contract.  Queries the KB for rows linked to this ingest so severity and gate
    vulnerabilities are derived from real data, not hard-coded placeholders.

    maybe_fire_tgep_for_report only fires when:
      - recommended_action == "PATCH"  AND
      - severity in {"HIGH", "CRITICAL"}
    """
    from app.knowledge.kb_store import query_evasions

    # Fetch all evasion rows for this ingest (up to 1000)
    linked = [e for e in query_evasions(limit=1000) if e.get("ingest_log_id") == ingest_id]

    # Derive max severity
    severity_order = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
    max_sev_value = max(
        (severity_order.get(e.get("severity", "LOW"), 1) for e in linked),
        default=0,
    )
    severity_map = {4: "CRITICAL", 3: "HIGH", 2: "MEDIUM", 1: "LOW", 0: "NONE"}
    max_severity = severity_map[max_sev_value]

    # Derive recommended_action
    if max_sev_value >= 3:        # HIGH or CRITICAL
        recommended_action = "PATCH"
    elif max_sev_value == 2:      # MEDIUM
        recommended_action = "MONITOR"
    else:
        recommended_action = "ACCEPT"

    # Collect distinct gate vulnerabilities
    gates: set[str] = set()
    for ev in linked:
        for g in ev.get("gate_bypassed") or []:
            if g:
                gates.add(g)

    import uuid as _uuid
    from datetime import datetime, timezone
    return {
        "id": str(_uuid.uuid4()),
        "severity": max_severity,
        "recommended_action": recommended_action,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "archetype": archetype,
            "evasions_found": len(linked),
            "gate_vulnerabilities": sorted(gates),
            "gate_vulnerability": next(iter(sorted(gates)), None),
            "ingest_id": ingest_id,
            "evasion_ids": evasion_ids,
        },
    }

