"""
API Router — GET /red-team/report/{ingest_id}
===============================================
Returns full evasion analysis for a given ingest_id:
mutations tried, evasions found, gate vulnerabilities, recommended action.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.ingest.router import get_ingest_log
from app.knowledge.kb_store import query_evasions
from app.core.utils.audit_logger import get_logger
from app.core.utils.auth import require_api_key

log = get_logger(__name__)

router = APIRouter(
    prefix="/red-team",
    tags=["reports"],
)


@router.get(
    "/report/{ingest_id}",
    summary="Get full evasion analysis for an ingest",
    response_description="Full evasion report with mutations, gate vulnerabilities, and recommended action",
)
async def get_report(
    ingest_id: str,
    _key: str = Depends(require_api_key),
) -> dict[str, Any]:
    """
    Return the full Red Team evasion analysis for a given `ingest_id`.

    Includes:
    - The original ingest record
    - All evasion_kb entries linked to this ingest
    - Gate vulnerabilities discovered
    - Recommended action (PATCH | MONITOR | ACCEPT)

    Returns **404** if the ingest_id is not found.
    """
    # Find the ingest log entry
    ingest_log = get_ingest_log()
    ingest_entry = next((e for e in ingest_log if e["id"] == ingest_id), None)

    if ingest_entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ingest ID '{ingest_id}' not found",
        )

    # Gather evasion_kb entries linked to this ingest
    all_evasions = query_evasions(limit=1000)
    linked_evasions = [
        e for e in all_evasions if e.get("ingest_log_id") == ingest_id
    ]

    # Summarise gate vulnerabilities found
    gates_found: set[str] = set()
    for ev in linked_evasions:
        for g in ev.get("gate_bypassed") or []:
            gates_found.add(g)

    # Determine recommended action from highest severity evasion
    severity_order = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
    max_severity = max(
        (severity_order.get(e.get("severity", "LOW"), 1) for e in linked_evasions),
        default=0,
    )
    severity_label = {4: "CRITICAL", 3: "HIGH", 2: "MEDIUM", 1: "LOW", 0: "NONE"}.get(
        max_severity, "NONE"
    )

    if max_severity >= 3:  # HIGH or CRITICAL
        recommended_action = "PATCH"
    elif max_severity == 2:  # MEDIUM
        recommended_action = "MONITOR"
    else:
        recommended_action = "ACCEPT"

    report = {
        "ingest_id": ingest_id,
        "source_type": ingest_entry.get("source_type"),
        "priority": ingest_entry.get("priority"),
        "received_at": ingest_entry.get("received_at"),
        "status": ingest_entry.get("status"),
        "evasions_found": len(linked_evasions),
        "max_severity": severity_label,
        "recommended_action": recommended_action,
        "gate_vulnerabilities": sorted(gates_found),
        "evasion_details": linked_evasions,
    }

    log.info(
        "report_served",
        ingest_id=ingest_id,
        evasions_found=len(linked_evasions),
        recommended_action=recommended_action,
    )
    return report
