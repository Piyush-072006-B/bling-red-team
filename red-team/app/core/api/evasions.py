"""
API Router — GET /red-team/evasions
======================================
Paginated list of evasion_kb entries.
Query params: severity, archetype, gate, limit (default 20), offset.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, status

from app.knowledge.kb_store import query_evasions
from app.core.utils.audit_logger import get_logger
from app.core.utils.auth import require_api_key

log = get_logger(__name__)

router = APIRouter(
    prefix="/red-team",
    tags=["evasions"],
)


@router.get(
    "/evasions",
    summary="List evasion knowledge base entries",
    response_description="Paginated list of evasion_kb entries, most recent first",
)
async def list_evasions(
    severity: str | None = Query(
        default=None,
        description="Filter by severity: LOW | MEDIUM | HIGH | CRITICAL",
    ),
    archetype: str | None = Query(
        default=None,
        description="Filter by archetype name (e.g. 'structuring', 'digital_arrest')",
    ),
    gate: str | None = Query(
        default=None,
        description="Filter to entries where this gate was bypassed "
        "(cycle | sink | bipartite | cash_mule_sink | merchant_terminal)",
    ),
    limit: int = Query(
        default=20,
        ge=1,
        le=200,
        description="Max rows to return (1–200)",
    ),
    offset: int = Query(
        default=0,
        ge=0,
        description="Number of rows to skip (for pagination)",
    ),
    _key: str = Depends(require_api_key),
) -> dict[str, Any]:
    """
    Return a paginated list of evasion knowledge base entries, most recent first.

    **Filters** (all optional, combinable):
    - `severity`: LOW | MEDIUM | HIGH | CRITICAL
    - `archetype`: one of the 16 known archetypes or NEW_VARIANT
    - `gate`: one of the 5 hard gate names
    - `limit`: max results (default 20, max 200)
    - `offset`: pagination offset
    """
    evasions = query_evasions(
        severity=severity,
        archetype=archetype,
        gate=gate,
        limit=limit,
        offset=offset,
    )

    log.info(
        "evasions_listed",
        count=len(evasions),
        severity=severity,
        archetype=archetype,
        gate=gate,
    )

    return {
        "total_returned": len(evasions),
        "limit": limit,
        "offset": offset,
        "filters": {
            "severity": severity,
            "archetype": archetype,
            "gate": gate,
        },
        "evasions": evasions,
    }
