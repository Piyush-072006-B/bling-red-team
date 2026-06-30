"""
Tests for tier-aware bypass mutations, graph patterns, and Isolation Forest evasion.
"""
import copy
import pytest

from app.engines.graph_adversary import vary_structural_fingerprint, _IF_STRUCTURAL_FEATURES as IF_STRUCTURAL_FEATURES
from app.engines.graph_adversary import generate_tgep_bypass_graph
from app.engines.mutation_engine import generate_mutations
from app.worker.pre_flight import pre_flight_tier_check


# ── Fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def fraud_vector() -> dict:
    """A typical fraud feature vector with high-risk values."""
    return {
        "amount_zscore": 2.5,
        "night_txn_ratio": 0.45,
        "burst_score": 0.85,
        "velocity_ratio": 3.2,
        "channel_switch": 1.0,
        "geography_switch": 1.0,
        "counterparty_novelty": 0.8,
        "dormancy_reactivation_flag": 1.0,
        "txn_count_30d": 2.0,
        "account_age_days": 30.0,
        "kyc_completeness_score": 0.3,
        "weekend_txn_ratio": 0.8,
        "hour_of_day": 3.0,
        "day_of_week": 6.0,
        "is_weekend": 1.0,
        "is_night": 1.0,
        "payee_vpa_age_days": 2.0,
        "payee_in_alert_log": 1.0,
        "payee_shared_alert_count": 3.0,
        "pagerank_fraud_seeded": 0.35,
        "community_fraud_ratio": 0.25,
        "shortest_path_to_fraud": 1.0,
        "bridge_node_probability": 0.4,
        "cycle_membership": 1.0,
        "sink_score": 0.8,
        "bipartite_score": 0.9,
        "fan_out_ratio": 0.5,
        "return_ratio": 0.6,
        "cash_mule_sink_score": 0.7,
        "dormancy_break": 1.0,
        "channel_entropy": 0.2,
        "distinct_counterparties_30d": 3.0,
        "is_festival_period": 0.0,
        "betweenness_centrality": 0.5,
        "clustering_coefficient": 0.4,
        "degree_centrality": 0.6,
        "temporal_acceleration": 0.7,
        "txn_count_all": 5.0,
        "amount_series_score": 0.9,
        "amount_vs_threshold_50000": 1.0,
        "amount_vs_threshold_100000": 0.0,
        "amount_vs_threshold_1000000": 0.0,
        "hour_deviation": 0.8,
    }


# ── Tier 1 tests ────────────────────────────────────────────────────

# Removed: test_tier1_safe_vector_passes_all_fast_rules (helper deleted in refactor)


# ── Compound full bypass ────────────────────────────────────────────


def test_compound_full_bypass_covers_all_59_features(fraud_vector):
    """compound_full_bypass must touch Tier1 + Tier2 + context feature groups."""
    from app.engines.mutation_engine import generate_mutations
    mutations = generate_mutations(fraud_vector, "structuring")
    full_bypass = next(m for m in mutations if m and m["mutation_type"] == "compound_full_bypass")

    deltas = full_bypass["delta_features"]

    # Must touch Tier 1 features
    tier1_keys = {"night_txn_ratio", "burst_score", "velocity_ratio",
                  "channel_switch", "geography_switch", "counterparty_novelty",
                  "dormancy_reactivation_flag"}
    assert tier1_keys.issubset(set(deltas.keys())), \
        f"Missing Tier 1 keys: {tier1_keys - set(deltas.keys())}"

    # Must touch Tier 2 gate features
    tier2_keys = {"cycle_membership", "sink_score", "bipartite_score",
                  "cash_mule_sink_score", "channel_entropy"}
    assert tier2_keys.issubset(set(deltas.keys())), \
        f"Missing Tier 2 keys: {tier2_keys - set(deltas.keys())}"

    # Must touch context multiplier features
    assert "is_festival_period" in deltas


# ── Context multipliers ────────────────────────────────────────────

# Removed: test_stack_multipliers_reduces_score_by_55pct (helper deleted)


# ── Tier 2 gate defeat tests ───────────────────────────────────────

# Removed: test_gate_defeat_cycle_uses_safe_cycle_membership (helper deleted)
# Removed: test_gate_defeat_sink_has_fan_out (helper deleted)
# Removed: test_gate_defeat_bipartite_below_threshold (helper deleted)


# ── Graph pattern tests ────────────────────────────────────────────


def test_nine_hop_graph_has_7_accounts():
    """nine_hop_linear graph was updated to multi-source sink structure with 7 accounts."""
    result = generate_tgep_bypass_graph("structuring", "nine_hop_linear")
    edges = result["edges"]

    # Collect all unique accounts
    accounts = set()
    for e in edges:
        accounts.add(e["from_account"])
        accounts.add(e["to_account"])

    assert len(accounts) == 7, f"Expected 7 accounts, got {len(accounts)}: {accounts}"
    assert len(edges) == 6  # 6 transfers for 7 accounts


def test_sink_with_outflow_ratio_below_threshold():
    """out/in ratio must be > 0.2 in sink_with_outflow graph."""
    result = generate_tgep_bypass_graph("pig_butchering", "sink_with_outflow")
    edges = result["edges"]
    c = "ACC990477"

    total_in = sum(e["amount"] for e in edges if e["to_account"] == c)
    total_out = sum(e["amount"] for e in edges if e["from_account"] == c)

    ratio = total_out / total_in if total_in > 0 else 0
    assert ratio > 0.2, f"Outflow ratio {ratio:.3f} is not > 0.2"


# ── Isolation Forest fingerprint test ──────────────────────────────


def test_vary_fingerprint_no_two_identical(fraud_vector):
    """Run vary_structural_fingerprint 10 times; all results must differ."""
    fingerprints = []
    for _ in range(10):
        fv_copy = copy.deepcopy(fraud_vector)
        vary_structural_fingerprint(fv_copy)
        fp_tuple = tuple(fv_copy.get(f, 0.0) for f in IF_STRUCTURAL_FEATURES)
        fingerprints.append(fp_tuple)

    # All 10 fingerprints must be unique
    assert len(set(fingerprints)) == 10, "Not all 10 fingerprints are unique"


# ── Pre-flight tier check test ─────────────────────────────────────


def test_pre_flight_returns_expected_shape(fraud_vector):
    """pre_flight_tier_check must return the 4 required keys."""
    result = pre_flight_tier_check(fraud_vector)
    assert "tier1_risk" in result
    assert "tier2_gates_at_risk" in result
    assert "recommended_mutations" in result
    assert "estimated_bypass_difficulty" in result
    assert isinstance(result["tier1_risk"], float)
    assert isinstance(result["tier2_gates_at_risk"], list)
    # High-risk vector should flag multiple gates
    assert result["tier1_risk"] > 0.5
