"""
TGEP Client — Send Transaction Graphs to TGEP and Retrieve Analysis Results
============================================================================
Calls TGEP's public API. No authentication required on TGEP.

Endpoints:
    POST /transaction/manual      — submit a list of transaction edges
    POST /api/evidence/generate   — request PDF/JSON evidence package
    GET  /api/evidence/download/{filename}  — download evidence file
    GET  /api/graph/state         — get current graph state / Blue Team verdict
"""

from __future__ import annotations

from typing import Any

import httpx

from app.config import get_settings
from app.utils.audit_logger import get_logger

log = get_logger(__name__)

_TIMEOUT = 10.0


def _tgep_base() -> str:
    return get_settings().tgep_base_url


async def send_to_tgep(graph: list[dict[str, Any]]) -> dict[str, Any]:
    """POST transaction edges to TGEP /transaction/manual. Returns full TGEP response."""
    url = f"{_tgep_base()}/transaction/manual"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(url, json={"transactions": graph})
            resp.raise_for_status()
            result: dict[str, Any] = resp.json()
            log.info("tgep_graph_sent", edge_count=len(graph), status=resp.status_code)
            return result
    except Exception as exc:
        log.warning("tgep_send_failed", error=str(exc))
        return {"error": str(exc), "status": "unreachable"}


async def request_evidence(graph_id: str | None = None) -> dict[str, Any]:
    """POST to TGEP /api/evidence/generate. Returns {json_file, pdf_file, download_url}."""
    url = f"{_tgep_base()}/api/evidence/generate"
    body: dict[str, Any] = {}
    if graph_id:
        body["graph_id"] = graph_id
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(url, json=body)
            resp.raise_for_status()
            result: dict[str, Any] = resp.json()
            log.info("tgep_evidence_requested", graph_id=graph_id)
            return result
    except Exception as exc:
        log.warning("tgep_evidence_failed", error=str(exc))
        return {"error": str(exc), "status": "unreachable"}


async def get_tgep_verdict() -> dict[str, Any]:
    """GET TGEP /api/graph/state. Returns current graph state including Blue Team verdict."""
    url = f"{_tgep_base()}/api/graph/state"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            result: dict[str, Any] = resp.json()
            log.info("tgep_verdict_retrieved")
            return result
    except Exception as exc:
        log.warning("tgep_verdict_failed", error=str(exc))
        return {"error": str(exc), "status": "unreachable"}


async def clear_tgep_graph() -> None:
    """POST /graph/clear to reset TGEP graph state between attacks (if enabled in config)."""
    if not get_settings().tgep_clear_graph_between_attacks:
        return
    url = f"{_tgep_base()}/graph/clear"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            await client.post(url)
            log.info("tgep_graph_cleared")
    except Exception as exc:
        log.warning("tgep_clear_failed", error=str(exc))
