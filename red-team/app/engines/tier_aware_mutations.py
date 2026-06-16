"""
Tier-Aware Mutations — Evasion strategies targeting specific Blue Team tiers
=============================================================================
"""

from __future__ import annotations

import copy
from typing import Any

from app.engines.mutation_engine import build_mutation


def generate_tier1_safe_vector(feature_vector: dict[str, float]) -> dict[str, float]:
    """Clamp or set 23 features to Tier-1 safe ranges."""
    fv = copy.deepcopy(feature_vector)
    
    # Clamping and setting specific safe ranges
    if fv.get("amount_zscore", 0) > 1.2:
        fv["amount_zscore"] = 1.2
    
    overrides = {
        "night_txn_ratio": 0.05,
        "burst_score": 0.25,
        "velocity_ratio": 1.1,
        "channel_switch": 0.0,
        "geography_switch": 0.0,
        "counterparty_novelty": 0.1,
        "dormancy_reactivation_flag": 0.0,
        "txn_count_30d": 18.0,
        "account_age_days": 730.0,
        "kyc_completeness_score": 0.95,
        "weekend_txn_ratio": 0.3,
        "hour_of_day": 14.0,
        "day_of_week": 2.0,
        "is_weekend": 0.0,
        "is_night": 0.0,
        "payee_vpa_age_days": 180.0,
        "payee_in_alert_log": 0.0,
        "payee_shared_alert_count": 0.0,
        "pagerank_fraud_seeded": 0.05,
        "community_fraud_ratio": 0.02,
        "shortest_path_to_fraud": 6.0,
        "bridge_node_probability": 0.05,
    }
    fv.update(overrides)
    return fv


def stack_context_multipliers(feature_vector: dict[str, float], target_multiplier: float | None = None) -> dict[str, float]:
    """Stack Indian context multipliers to maximally reduce XGBoost output."""
    fv = copy.deepcopy(feature_vector)
    # Always set festival
    fv["is_festival_period"] = 1.0
    # Set gig worker if available in features (assume it's valid to set)
    fv["account_type_gig_worker"] = 1.0
    # Set rural + no geo switch
    fv["account_type_rural"] = 1.0
    fv["geography_switch"] = 0.0
    return fv


def defeat_tier2_gates(feature_vector: dict[str, float], gate_name: str | None = None) -> dict[str, float]:
    """Manipulate features to defeat Tier 2 gates and their legitimacy filters."""
    fv = copy.deepcopy(feature_vector)
    
    # cycle gate defeat
    if gate_name is None or gate_name == "cycle":
        fv["cycle_membership"] = 0.0
        fv["return_ratio"] = 0.02
        fv["kyc_completeness_score"] = 0.95  # Legitimacy

    # sink gate defeat
    if gate_name is None or gate_name == "sink":
        fv["sink_score"] = 0.15
        fv["fan_out_ratio"] = 2.5
        fv["return_ratio"] = 0.45
        fv["txn_count_30d"] = 20.0  # Legitimacy

    # bipartite gate defeat
    if gate_name is None or gate_name == "bipartite":
        fv["bipartite_score"] = 0.4
        fv["distinct_counterparties_30d"] = 25.0
        # Use max 6 senders -> implicitly represented by bipartite score drops

    # cash_mule_sink defeat
    if gate_name is None or gate_name == "cash_mule_sink":
        fv["cash_mule_sink_score"] = 0.1
        fv["dormancy_break"] = 0.0
        fv["dormancy_reactivation_flag"] = 0.0

    # merchant_terminal defeat
    if gate_name is None or gate_name == "merchant_terminal":
        fv["channel_entropy"] = 0.8
        fv["return_ratio"] = 0.05

    return fv


# ── Compound Mutations ─────────────────────────────────────────────

def _compound_full_bypass(original: dict[str, float]) -> dict[str, Any] | None:
    fv = generate_tier1_safe_vector(original)
    fv = stack_context_multipliers(fv)
    fv = defeat_tier2_gates(fv)
    
    # Diff vs original to generate overrides
    overrides = {k: v for k, v in fv.items() if original.get(k) != v}
    return build_mutation("compound_full_bypass", original, overrides)


def _compound_clean_salary_profile(original: dict[str, float]) -> dict[str, Any] | None:
    overrides = {
        "txn_amount": 45000.0,
        "txn_count_30d": 22.0,
        "return_ratio": 0.0,
        "burst_score": 0.15,
        "velocity_ratio": 0.9,
        "kyc_completeness_score": 0.98,
        "account_age_days": 1095.0,
        "night_txn_ratio": 0.05,
        "amount_zscore": 0.8,
        "channel_upi": 1.0,
        "is_festival_period": 1.0,
    }
    return build_mutation("compound_clean_salary_profile", original, overrides)


def _compound_treasury_ghost(original: dict[str, float]) -> dict[str, Any] | None:
    overrides = {
        "counterparty_novelty": 0.0,
        "kyc_completeness_score": 0.99,
        "account_age_days": 2000.0,
        "community_fraud_ratio": 0.01,
        "pagerank_fraud_seeded": 0.02,
        "shortest_path_to_fraud": 8.0,
        "txn_count_30d": 30.0,
        "burst_score": 0.1,
        "velocity_ratio": 0.8,
        "amount_zscore": 0.5,
        "is_festival_period": 1.0,
    }
    return build_mutation("compound_treasury_ghost", original, overrides)


def _compound_gig_rural_festival(original: dict[str, float]) -> dict[str, Any] | None:
    overrides = {
        "is_festival_period": 1.0,
        "txn_count_30d": 8.0,
        "burst_score": 0.35,
        "velocity_ratio": 1.4,
        "channel_entropy": 0.7,
        "geography_switch": 0.0,
        "dormancy_break": 0.0,
        "night_txn_ratio": 0.08,
        "amount_zscore": 1.1,
        "counterparty_novelty": 0.15,
        "account_type_gig_worker": 1.0,
        "account_type_rural": 1.0,
    }
    return build_mutation("compound_gig_rural_festival", original, overrides)


def _compound_jandhan_first_timer(original: dict[str, float]) -> dict[str, Any] | None:
    overrides = {
        "txn_amount": 2000.0,
        "txn_count_30d": 1.0,
        "txn_count_all": 1.0,
        "account_age_days": 400.0,
        "kyc_completeness_score": 0.7,
        "counterparty_novelty": 1.0,
        "burst_score": 0.0,
        "velocity_ratio": 0.0,
        "channel_upi": 1.0,
        "is_festival_period": 0.0,
        "night_txn_ratio": 0.0,
    }
    return build_mutation("compound_jandhan_first_timer", original, overrides)


def _compound_low_slow_warmup(original: dict[str, float]) -> dict[str, Any] | None:
    overrides = {
        "txn_count_30d": 12.0,
        "avg_txn_amount_30d": 8000.0,
        "burst_score": 0.2,
        "velocity_ratio": 0.85,
        "dormancy_reactivation_flag": 0.0,
        "dormancy_break": 0.0,
        "amount_zscore": 0.6,
        "night_txn_ratio": 0.12,
        "txn_volume_last_24h": 15000.0,
        "distinct_payees_24h": 3.0,
        "is_festival_period": 1.0,
    }
    return build_mutation("compound_low_slow_warmup", original, overrides)


def generate_tier_aware_mutations(fv: dict[str, float]) -> list[dict[str, Any] | None]:
    """Return all new tier-aware compound mutations."""
    return [
        _compound_full_bypass(fv),
        _compound_clean_salary_profile(fv),
        _compound_treasury_ghost(fv),
        _compound_gig_rural_festival(fv),
        _compound_jandhan_first_timer(fv),
        _compound_low_slow_warmup(fv),
    ]
