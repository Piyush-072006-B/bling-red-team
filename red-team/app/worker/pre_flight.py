"""
Pre-Flight Tier Check — Estimates detection risk before mutation
================================================================
"""

from __future__ import annotations

from typing import Any

from app.core.utils.audit_logger import get_logger

log = get_logger(__name__)

# Tier 1 feature thresholds — if the value exceeds these, Tier 1 will flag
_TIER1_THRESHOLDS: dict[str, float] = {
    "amount_zscore": 1.5,
    "night_txn_ratio": 0.10,
    "burst_score": 0.30,
    "velocity_ratio": 1.3,
    "channel_switch": 0.5,
    "geography_switch": 0.5,
    "counterparty_novelty": 0.5,
    "dormancy_reactivation_flag": 0.5,
}

# Tier 2 gate trigger features
_TIER2_GATE_FEATURES: dict[str, dict[str, float]] = {
    "cycle": {"cycle_membership": 0.5},
    "sink": {"sink_score": 0.6},
    "bipartite": {"bipartite_score": 0.7},
    "cash_mule_sink": {"cash_mule_sink_score": 0.5},
    "merchant_terminal": {"return_ratio": 0.3},
}

_GATE_TO_MUTATION: dict[str, str] = {
    "cycle": "compound_full_bypass",
    "sink": "compound_full_bypass",
    "bipartite": "compound_full_bypass",
    "cash_mule_sink": "compound_low_slow_warmup",
    "merchant_terminal": "compound_full_bypass",
}


def pre_flight_tier_check(feature_vector: dict[str, float]) -> dict[str, Any]:
    """Estimate detection risk across Tier 1 and Tier 2 before mutations."""
    # Tier 1 risk = fraction of features that exceed thresholds
    flagged = 0
    for feat, threshold in _TIER1_THRESHOLDS.items():
        if feature_vector.get(feat, 0.0) > threshold:
            flagged += 1
    tier1_risk = round(flagged / len(_TIER1_THRESHOLDS), 2)

    # Tier 2 gate risk
    gates_at_risk: list[str] = []
    for gate, features in _TIER2_GATE_FEATURES.items():
        for feat, threshold in features.items():
            if feature_vector.get(feat, 0.0) >= threshold:
                gates_at_risk.append(gate)
                break

    # Recommended mutations
    recommended: list[str] = []
    if tier1_risk > 0.3:
        recommended.append("compound_full_bypass")
    for gate in gates_at_risk:
        mut = _GATE_TO_MUTATION.get(gate, "compound_full_bypass")
        if mut not in recommended:
            recommended.append(mut)
    if not recommended:
        recommended.append("compound_treasury_ghost")

    # Difficulty estimation
    total_risk = tier1_risk + len(gates_at_risk) * 0.2
    if total_risk > 0.8:
        difficulty = "HARD"
    elif total_risk > 0.4:
        difficulty = "MEDIUM"
    else:
        difficulty = "EASY"

    result = {
        "tier1_risk": tier1_risk,
        "tier2_gates_at_risk": gates_at_risk,
        "recommended_mutations": recommended,
        "estimated_bypass_difficulty": difficulty,
    }

    log.info("pre_flight_tier_check", **result)
    return result
