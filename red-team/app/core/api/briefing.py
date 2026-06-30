"""
API Router — GET /red-team/briefing
=====================================
Thin FastAPI route. All business logic lives in app.services.briefing_service.

Auth: X-API-Key (same as all other endpoints).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.core.utils.auth import require_api_key
from app.services.briefing_service import build_briefing

router = APIRouter(prefix="/red-team", tags=["briefing"])


@router.get(
    "/briefing",
    summary="Red Team intelligence briefing for Blue Team developers",
    response_description=(
        "Human-readable JSON briefing: immediate actions, monitoring items, "
        "top exploitable features, and context multiplier risks."
    ),
)
async def get_briefing(
    _key: str = Depends(require_api_key),
) -> dict[str, Any]:
    """
    Return a single synthesised intelligence briefing from the entire evasion KB.

    **Sections:**
    - `immediate_action_required` — CRITICAL evasions with confirmed evasion_success.
    - `monitor` — HIGH-severity evasions requiring attention.
    - `structural_findings` — Structural evasion patterns; shadow scorer offline, severity unconfirmed.
    - `top_exploitable_features` — top-3 most frequently exploited features.
    - `context_multipliers_at_risk` — Indian context multipliers that were successfully abused.

    **Golden invariant:** Developer intelligence only — no automated action triggered.
    """
    return build_briefing()


