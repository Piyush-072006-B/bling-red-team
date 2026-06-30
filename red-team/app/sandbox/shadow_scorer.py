"""
Shadow Scorer Client — Read-Only Blue Team Score Simulation
=============================================================
HTTP client using httpx that POSTs mutated transactions to the Blue Team
shadow scorer endpoint only. Never calls production Blue Team scorer.

INVARIANT: Only calls BLUE_TEAM_SHADOW_URL/api/v1/shadow/score
           Never calls /api/v1/score (production endpoint).

Parses response: extracts score, action, gate_fired.
Timeout: 5 seconds.
On failure: logs error, returns {"score": null, "error": "shadow_scorer_unavailable"}.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.config import get_settings
from app.core.utils.audit_logger import get_logger

log = get_logger(__name__)

# Shadow endpoint path (must never be changed to the production scorer path)
_SHADOW_ENDPOINT_PATH = "/api/v1/shadow/score"


async def score_transaction(
    mutated_vector: dict[str, float],
    *,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    POST a (mutated) feature vector to the Blue Team shadow scorer.

    Args:
        mutated_vector: Feature vector dict to score.
        metadata:       Optional extra context fields to include in the payload
                        (e.g. mutation_id, archetype). NOT used for scoring;
                        passed through for traceability.

    Returns:
        On success:
            {
                "score":      float,   # 0.0–1.0 fraud probability
                "action":     str,     # BLOCK | REVIEW | PASS
                "gate_fired": str | None,  # gate name or None
                "raw":        dict,    # full response body
            }
        On failure:
            {
                "score":  None,
                "action": None,
                "gate_fired": None,
                "error":  "shadow_scorer_unavailable",
                "detail": str,  # exception message
            }
    """
    settings = get_settings()
    shadow_url = settings.blue_team_shadow_url.strip()

    # Guard: if no shadow URL is configured, return immediately without HTTP call
    if not shadow_url:
        log.debug("shadow_scorer_not_configured")
        return {
            "score": None,
            "action": None,
            "gate_fired": None,
            "error": "shadow_scorer_not_configured",
            "detail": "BLUE_TEAM_SHADOW_URL is not set. Configure it to point to Blue Team.",
        }

    shadow_url = shadow_url.rstrip("/") + _SHADOW_ENDPOINT_PATH

    payload: dict[str, Any] = {"feature_vector": mutated_vector}
    if metadata:
        payload["metadata"] = metadata

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                shadow_url,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "X-Caller": "red-team-sandbox",
                    "X-API-Key": settings.blue_team_shadow_api_key,
                },
            )
            response.raise_for_status()
            body = response.json()

        score = float(body.get("score", 0.0))
        action = body.get("action")
        gate_fired = body.get("gate_fired")

        log.info(
            "shadow_score_received",
            score=round(score, 4),
            action=action,
            gate_fired=gate_fired,
        )

        return {
            "score": score,
            "action": action,
            "gate_fired": gate_fired,
            "raw": body,
        }

    except httpx.TimeoutException as exc:
        log.warning("shadow_scorer_timeout", url=shadow_url, detail=str(exc))
        return _unavailable("timeout", str(exc))

    except httpx.HTTPStatusError as exc:
        log.warning(
            "shadow_scorer_http_error",
            status_code=exc.response.status_code,
            url=shadow_url,
        )
        return _unavailable(
            "http_error",
            f"HTTP {exc.response.status_code}: {exc.response.text[:200]}",
        )

    except httpx.RequestError as exc:
        log.warning("shadow_scorer_connection_error", url=shadow_url, detail=str(exc))
        return _unavailable("connection_error", str(exc))

    except Exception as exc:
        log.error("shadow_scorer_unexpected_error", detail=str(exc))
        return _unavailable("unexpected_error", str(exc))


def _unavailable(reason: str, detail: str) -> dict[str, Any]:
    """Return a standardised unavailable response."""
    return {
        "score": None,
        "action": None,
        "gate_fired": None,
        "error": "shadow_scorer_unavailable",
        "reason": reason,
        "detail": detail,
    }
