"""
Attack Package — Assembles Output Package per Evasion and Persists Graph JSON
=============================================================================
Combines the TGEP graph, TGEP response, feature deltas, and a plain-English
bypass strategy description into one self-contained attack package.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.outputs.graph_exporter import get_graph_for_mutation
from app.core.utils.audit_logger import get_logger

log = get_logger(__name__)

# Output directory — one level above app/ inside red-team/
_OUTPUT_DIR = Path(__file__).parent.parent.parent / "outputs"

# Human-readable bypass strategy descriptions keyed by mutation_type prefix
_STRATEGY_MAP: dict[str, str] = {
    "threshold_amount_50k": "Amount reduced to 92% of ₹50K threshold to avoid structuring flag.",
    "threshold_amount_100k": "Amount reduced to 92% of ₹1L threshold.",
    "threshold_amount_1m": "Amount reduced to 92% of ₹10L threshold.",
    "timing_day": "Transaction timing shifted to daytime (9–18h) to avoid night_txn_ratio flag.",
    "velocity_20pct": "Transaction velocity reduced by 20% to avoid burst detection.",
    "velocity_30pct": "Transaction velocity reduced by 30%.",
    "velocity_40pct": "Transaction velocity reduced by 40%.",
    "context_festival": "is_festival_period set to 1 to exploit 0.70× Blue Team multiplier.",
    "context_senior": "Night flag removed to exploit senior-account exemption.",
    "novelty_zero": "counterparty_novelty set to 0 — payee treated as known counterparty.",
    "compound_daytime_slowdown": "Daytime + 30% velocity reduction combined to bypass timing gates.",
    "compound_structuring_ghost": "Sub-threshold amounts + known counterparty — classic ghost structuring.",
    "compound_festival_layering": "Festival context + velocity reduction — exploits seasonal multipliers.",
    "compound_mule_warmup": "Warm account history created to remove dormancy flag.",
    "compound_kyc_ghost": "High KYC + no geography/channel switches — mimics clean corporate account.",
    "compound_senior_festival_night": "Night removed + festival flag — exploits senior + seasonal exemptions.",
    "compound_full_bypass": "Full 3-tier bypass: Tier1 safe + all context multipliers + all Tier2 gates neutralised.",
    "compound_clean_salary_profile": "Salary account profile cloned — looks like recurring NEFT salary.",
    "compound_treasury_ghost": "Treasury/internal account profile — bypasses all legitimacy filters.",
    "compound_gig_rural_festival": "Gig+rural+festival triple multiplier stack (×0.446 effective).",
    "compound_jandhan_first_timer": "Jan Dhan first-time profile — low amounts, high novelty forgiven.",
    "compound_low_slow_warmup": "Low-slow mule warmup phase — avoids burst and dormancy sensors.",
    "graph_bypass_mule_warmup_graph": "30-day warmup graph then large spike — cash mule gate bypass.",
    "graph_bypass_nine_hop_linear": "9-hop linear chain — outside Blue Team's 2-8 hop cycle detection window.",
    "graph_bypass_sink_with_outflow": "Corporate inflows + legitimate outflows — reduces sink_score below 0.6.",
    "graph_bypass_slow_bipartite": "6 senders (below 7 threshold) over 5 days — bipartite gate not triggered.",
}

_DEFAULT_STRATEGY = "Evasion mutation applied — see feature_deltas for details."


def _bypass_strategy(mutation_type: str | None) -> str:
    if not mutation_type:
        return _DEFAULT_STRATEGY
    for prefix, desc in _STRATEGY_MAP.items():
        if mutation_type == prefix:
            return desc
    return _DEFAULT_STRATEGY


def build_attack_package(evasion: dict[str, Any], archetype: str) -> dict[str, Any]:
    """Assemble a complete attack package for one evasion KB row."""
    mutation_type: str | None = evasion.get("mutation_type")
    evasion_vector: dict[str, float] = evasion.get("evasion_vector") or {}

    tgep_graph = get_graph_for_mutation(
        mutation_type=mutation_type or "",
        evasion_vector=evasion_vector,
        archetype=archetype,
    )

    return {
        "attack_id": str(uuid.uuid4()),
        "archetype": archetype,
        "mutation_type": mutation_type,
        "tgep_graph": tgep_graph,
        "tgep_response": evasion.get("tgep_response"),
        "tgep_verdict": evasion.get("tgep_threat_level"),
        "feature_deltas": evasion.get("feature_deltas", {}),
        "bypass_strategy": _bypass_strategy(mutation_type),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def package_to_json_file(package: dict[str, Any]) -> str:
    """Write package's tgep_graph to outputs/{archetype}_{mutation_type}_{ts}.json. Returns path."""
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    archetype = package.get("archetype", "unknown")
    mutation_type = (package.get("mutation_type") or "mutation").replace("/", "_")
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    filename = f"{archetype}_{mutation_type}_{ts}.json"
    file_path = _OUTPUT_DIR / filename

    with open(file_path, "w", encoding="utf-8") as fh:
        json.dump(package["tgep_graph"], fh, indent=2)

    log.info("attack_graph_saved", path=str(file_path), edge_count=len(package["tgep_graph"]))
    return str(file_path)
