"""
Mutation Engine (Refactored: Faster, Smaller, Cleaner)
======================================================
Generates up to 22 evasion mutations using a declarative ruleset.
Replaces 500+ lines of scattered boilerplate with a single O(1) rules dict.
"""

from __future__ import annotations
import copy
import uuid
from typing import Any, Callable
from app.core.utils.audit_logger import get_logger

log = get_logger(__name__)

def _clamp(v: float) -> float:
    return max(0.0, min(1.0, v))

def _build_mutation(
    mtype: str, orig: dict[str, float], apply_fn: Callable[[dict[str, float]], None]
) -> dict[str, Any] | None:
    mutated = copy.deepcopy(orig)
    apply_fn(mutated)
    
    for k, v in mutated.items():
        if k in orig and orig[k] == v: continue
        mutated[k] = _clamp(v) if v <= 1.0 else v
        
    delta = {k: round(mutated[k] - orig.get(k, 0.0), 6) for k in mutated if mutated[k] != orig.get(k)}
    injected = [k for k in mutated if k not in orig]
    
    if not delta and not injected: return None
        
    return {
        "mutation_id": str(uuid.uuid4()),
        "mutation_type": mtype,
        "delta_features": delta,
        "injected_features": injected,
        "original_vector": copy.deepcopy(orig),
        "mutated_vector": mutated,
    }

def _thresh(v: dict, k: str):
    v[k] = v.get(k, 1.0) * 0.92 if v.get(k, 0) > 0 else 0.85 * 0.92

def _full_bypass(v: dict):
    if v.get("amount_zscore", 0) > 1.2: v["amount_zscore"] = 1.2
    v.update({
        "night_txn_ratio": 0.05, "burst_score": 0.25, "velocity_ratio": 1.1,
        "channel_switch": 0.0, "geography_switch": 0.0, "counterparty_novelty": 0.1,
        "dormancy_reactivation_flag": 0.0, "txn_count_30d": 18.0, "account_age_days": 730.0,
        "kyc_completeness_score": 0.95, "weekend_txn_ratio": 0.3, "hour_of_day": 14.0,
        "day_of_week": 2.0, "is_weekend": 0.0, "is_night": 0.0, "payee_vpa_age_days": 180.0,
        "payee_in_alert_log": 0.0, "payee_shared_alert_count": 0.0, "pagerank_fraud_seeded": 0.05,
        "community_fraud_ratio": 0.02, "shortest_path_to_fraud": 6.0, "bridge_node_probability": 0.05,
        "is_festival_period": 1.0, "account_type_gig_worker": 1.0, "account_type_rural": 1.0,
        "cycle_membership": 0.0, "return_ratio": 0.05, "sink_score": 0.15, "fan_out_ratio": 2.5,
        "bipartite_score": 0.4, "distinct_counterparties_30d": 25.0, "cash_mule_sink_score": 0.1,
        "dormancy_break": 0.0, "channel_entropy": 0.8
    })

RULES: dict[str, Callable[[dict], None]] = {
    # 1. Single Feature
    "threshold_amount_50k": lambda v: [_thresh(v, "amount_vs_threshold_50000"), _thresh(v, "amount_series_score")],
    "threshold_amount_100k": lambda v: _thresh(v, "amount_vs_threshold_100000"),
    "threshold_amount_1m": lambda v: _thresh(v, "amount_vs_threshold_1000000"),
    "timing_day": lambda v: v.update({"night_txn_ratio": 0.15, "hour_deviation": 0.0}),
    "velocity_20pct": lambda v: v.update({"burst_score": v.get("burst_score",1.0)*0.8, "velocity_ratio": v.get("velocity_ratio",1.0)*0.8}),
    "velocity_30pct": lambda v: v.update({"burst_score": v.get("burst_score",1.0)*0.7, "velocity_ratio": v.get("velocity_ratio",1.0)*0.7}),
    "velocity_40pct": lambda v: v.update({"burst_score": v.get("burst_score",1.0)*0.6, "velocity_ratio": v.get("velocity_ratio",1.0)*0.6}),
    "context_festival": lambda v: v.update({"is_festival_period": 1.0}),
    "context_senior": lambda v: v.update({"night_txn_ratio": 0.0}),
    "novelty_zero": lambda v: v.update({"counterparty_novelty": 0.0}),
    
    # 2. Compound Features
    "compound_daytime_slowdown": lambda v: v.update({"night_txn_ratio": 0.1, "hour_deviation": 0.0, "burst_score": v.get("burst_score",1.0)*0.7, "velocity_ratio": v.get("velocity_ratio",1.0)*0.7, "channel_entropy": 0.3}),
    "compound_structuring_ghost": lambda v: v.update({"amount_series_score": v.get("amount_series_score",1.0)*0.88, "amount_vs_threshold_50000": v.get("amount_vs_threshold_50000",1.0)*0.88, "counterparty_novelty": 0.0, "txn_count_30d": 3.0}),
    "compound_festival_layering": lambda v: v.update({"is_festival_period": 1.0, "velocity_ratio": v.get("velocity_ratio",1.0)*0.75, "burst_score": v.get("burst_score",1.0)*0.75, "night_txn_ratio": 0.1}),
    "compound_mule_warmup": lambda v: v.update({"dormancy_reactivation_flag": 0.0, "txn_count_30d": 12.0, "avg_txn_amount_30d": 15000.0, "burst_score": v.get("burst_score",1.0)*0.6}),
    "compound_kyc_ghost": lambda v: v.update({"kyc_completeness_score": 0.9, "counterparty_novelty": 0.0, "geography_switch": 0.0, "channel_switch": 0.0}),
    "compound_senior_festival_night": lambda v: v.update({"night_txn_ratio": 0.0, "is_festival_period": 1.0, "payee_vpa_age_days": 30.0, "amount_zscore": 1.5}),
    
    # 3. Tier-Aware Features
    "compound_full_bypass": _full_bypass,
    "compound_clean_salary_profile": lambda v: v.update({"txn_amount": 45000.0, "txn_count_30d": 22.0, "return_ratio": 0.0, "burst_score": 0.15, "velocity_ratio": 0.9, "kyc_completeness_score": 0.98, "account_age_days": 1095.0, "night_txn_ratio": 0.05, "amount_zscore": 0.8, "channel_upi": 1.0, "is_festival_period": 1.0}),
    "compound_treasury_ghost": lambda v: v.update({"counterparty_novelty": 0.0, "kyc_completeness_score": 0.99, "account_age_days": 2000.0, "community_fraud_ratio": 0.01, "pagerank_fraud_seeded": 0.02, "shortest_path_to_fraud": 8.0, "txn_count_30d": 30.0, "burst_score": 0.1, "velocity_ratio": 0.8, "amount_zscore": 0.5, "is_festival_period": 1.0}),
    "compound_gig_rural_festival": lambda v: v.update({"is_festival_period": 1.0, "txn_count_30d": 8.0, "burst_score": 0.35, "velocity_ratio": 1.4, "channel_entropy": 0.7, "geography_switch": 0.0, "dormancy_break": 0.0, "night_txn_ratio": 0.08, "amount_zscore": 1.1, "counterparty_novelty": 0.15, "account_type_gig_worker": 1.0, "account_type_rural": 1.0}),
    "compound_jandhan_first_timer": lambda v: v.update({"txn_amount": 2000.0, "txn_count_30d": 1.0, "txn_count_all": 1.0, "account_age_days": 400.0, "kyc_completeness_score": 0.7, "counterparty_novelty": 1.0, "burst_score": 0.0, "velocity_ratio": 0.0, "channel_upi": 1.0, "is_festival_period": 0.0, "night_txn_ratio": 0.0}),
    "compound_low_slow_warmup": lambda v: v.update({"txn_count_30d": 12.0, "avg_txn_amount_30d": 8000.0, "burst_score": 0.2, "velocity_ratio": 0.85, "dormancy_reactivation_flag": 0.0, "dormancy_break": 0.0, "amount_zscore": 0.6, "night_txn_ratio": 0.12, "txn_volume_last_24h": 15000.0, "distinct_payees_24h": 3.0, "is_festival_period": 1.0}),
}

def generate_mutations(feature_vector: dict[str, float], archetype: str, n: int = 22) -> list[dict[str, Any]]:
    from app.engines.graph_adversary import vary_structural_fingerprint
    
    candidates = [_build_mutation(k, feature_vector, fn) for k, fn in RULES.items()]
    mutations = [m for m in candidates if m is not None]
    
    try:
        from app.engines.kb_feedback import get_mutation_weights, get_top_mutations
        weights = get_mutation_weights()
        if weights: mutations.sort(key=lambda m: weights.get(m.get("mutation_type", ""), 1.0), reverse=True)
    except Exception: pass

    result = mutations[:n]
    for m in result: vary_structural_fingerprint(m["mutated_vector"])
        
    log.info("mutations_generated", archetype=archetype, requested=n, produced=len(result))
    return result

def _prioritise_for_archetype(mutations, archetype): pass
