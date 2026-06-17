"""
API Router — GET /red-team/attack-graph/{ingest_id}
=====================================================
Returns all attack packages (TGEP graph JSON + bypass strategy) for an ingest.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.knowledge.kb_store import query_evasions
from app.outputs.attack_package import build_attack_package, package_to_json_file
from app.utils.audit_logger import get_logger
from app.utils.auth import require_api_key

log = get_logger(__name__)

router = APIRouter(
    prefix="/red-team",
    tags=["attack-graph"],
)


@router.get(
    "/attack-graph/{ingest_id}",
    summary="Get TGEP attack graph packages for an ingest",
    response_description="All attack packages for the given ingest ID",
)
async def get_attack_graph(
    ingest_id: str,
    _key: str = Depends(require_api_key),
) -> dict[str, Any]:
    """
    Return all TGEP transaction graph packages for every evasion linked to this ingest.

    Each package contains:
    - `mutation_type` — which evasion strategy was applied
    - `tgep_graph` — list of transaction edges in TGEP format
    - `bypass_strategy` — plain-English description of what the mutation does
    - `tgep_verdict` — TGEP threat level if already scored (null if TGEP is not connected)
    - `json_file_path` — path to the saved JSON file for manual TGEP submission
    """
    all_evasions = query_evasions(limit=1000)
    linked = [e for e in all_evasions if e.get("ingest_log_id") == ingest_id]

    if not linked:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No evasions found for ingest_id='{ingest_id}'",
        )

    archetype: str = linked[0].get("archetype", "NEW_VARIANT")
    packages = []

    for evasion in linked:
        try:
            pkg = build_attack_package(evasion, archetype)
            json_path = package_to_json_file(pkg)
            packages.append({
                "mutation_type": pkg["mutation_type"],
                "tgep_graph": pkg["tgep_graph"],
                "bypass_strategy": pkg["bypass_strategy"],
                "tgep_verdict": pkg["tgep_verdict"],
                "json_file_path": json_path,
            })
        except Exception as exc:
            log.warning("attack_graph_build_error", evasion_id=evasion.get("id"), error=str(exc))

    log.info(
        "attack_graph_retrieved",
        ingest_id=ingest_id,
        archetype=archetype,
        total=len(packages),
    )

    return {
        "ingest_id": ingest_id,
        "archetype": archetype,
        "attack_packages": packages,
        "total_attacks": len(packages),
    }
