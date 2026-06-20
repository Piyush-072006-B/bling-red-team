"""
Tests for seed library, self-generation, and dataset ingest schema.
"""

import pytest

from app.engines.seed_library import get_all_seeds, get_seed, get_seed_with_variation


# ─────────────────────────────────────────────────────────────────────────────
# Canonical 59 feature names (Blue Team feature vector)
# ─────────────────────────────────────────────────────────────────────────────

FEATURE_NAMES = {
    "amount_series_score", "txn_count_30d", "amount_vs_threshold_50000",
    "amount_vs_threshold_100000", "amount_vs_threshold_1000000",
    "burst_score", "velocity_ratio", "night_txn_ratio", "counterparty_novelty",
    "pagerank_fraud_seeded", "community_fraud_ratio", "sink_score",
    "return_ratio", "channel_entropy", "geography_switch",
    "dormancy_reactivation_flag", "kyc_completeness_score",
    "account_age_days", "txn_count_90d", "txn_count_all",
    "avg_txn_amount_30d", "distinct_counterparties_30d",
    "bipartite_score", "fan_out_ratio", "temporal_acceleration",
    "cash_mule_sink_score", "bridge_node_probability",
    "dormancy_break", "cycle_membership", "betweenness_centrality",
    "clustering_coefficient", "degree_centrality", "community_id",
    "shortest_path_to_fraud", "weekend_txn_ratio", "hour_deviation",
    "channel_switch", "amount_zscore", "txn_amount", "txn_amount_log",
    "txn_amount_rounded", "channel_upi", "channel_imps", "channel_rtgs",
    "channel_neft", "hour_of_day", "day_of_week", "is_weekend", "is_night",
    "is_festival_period", "payee_vpa_age_days", "txn_count_last_1h",
    "txn_count_last_24h", "txn_count_last_7d", "txn_volume_last_1h",
    "txn_volume_last_24h", "distinct_payees_24h",
    "payee_in_alert_log", "payee_shared_alert_count",
}

EXPECTED_ARCHETYPES = {
    "structuring", "digital_arrest", "rapid_layering", "bipartite_mule",
    "cycle_round_trip", "romance_scam", "pig_butchering", "merchant_terminal",
    "cash_in_mule", "otp_fraud", "investment_fraud", "account_takeover",
    "low_slow_mule", "salary_mule", "sim_swap", "ghost_node_cash",
}


# ─────────────────────────────────────────────────────────────────────────────
# Seed Library Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_all_16_archetypes_have_seeds():
    """All 16 archetypes must be present in the seed library."""
    seeds = get_all_seeds()
    assert len(seeds) == 16
    assert set(seeds.keys()) == EXPECTED_ARCHETYPES


def test_seed_has_59_features():
    """Every archetype seed must have exactly the 59 canonical features."""
    seeds = get_all_seeds()
    for archetype, seed in seeds.items():
        missing = FEATURE_NAMES - set(seed.keys())
        extra = set(seed.keys()) - FEATURE_NAMES
        assert not missing, f"{archetype} missing features: {missing}"
        assert not extra, f"{archetype} has extra features: {extra}"
        assert len(seed) == 59, f"{archetype} has {len(seed)} features, expected 59"


def test_get_seed_variation_differs_from_original():
    """Variation should change at least some numeric values."""
    original = get_seed("structuring")
    varied = get_seed_with_variation("structuring", variation_pct=0.15)
    diffs = sum(1 for k in original if original[k] != varied.get(k))
    assert diffs > 0, "Variation should change at least some values"


def test_get_seed_unknown_archetype_returns_structuring():
    """Unknown archetype falls back to structuring seed."""
    seed = get_seed("nonexistent_archetype")
    structuring = get_seed("structuring")
    assert seed == structuring


def test_self_generation_creates_valid_ingest_payload():
    """Self-generation payload must match FraudDNA schema."""
    from app.ingest.schemas import FraudDNA
    seed = get_seed_with_variation("digital_arrest")
    payload = FraudDNA(
        source_type="FRAUD_DNA",
        transaction_id="SELF_GEN_test_abc12345",
        account_id="SEED_ACC_digital_arrest",
        confirmed_archetype="digital_arrest",
        feature_vector=seed,
        shap_values={"amount_zscore": 4.2, "burst_score": 0.92},
        timestamp="2026-06-17T10:00:00Z",
    )
    assert payload.source_type == "FRAUD_DNA"
    assert payload.feature_vector == seed


def test_dataset_record_schema_validates_correctly():
    """DatasetRecord must validate and include all required fields."""
    from app.ingest.schemas import DatasetRecord
    record = DatasetRecord(
        source_type="DATASET",
        dataset_name="BAF_NeurIPS_2022",
        archetype="structuring",
        feature_vector=get_seed("structuring"),
        label="confirmed_fraud",
        original_record_id="BAF_00001",
    )
    assert record.source_type == "DATASET"
    assert record.dataset_name == "BAF_NeurIPS_2022"
    assert record.archetype == "structuring"
    assert record.label == "confirmed_fraud"
    assert record.original_record_id == "BAF_00001"
    assert len(record.feature_vector) == 59


def test_self_generated_structuring_seed_matches_structuring_archetype():
    """A structuring seed should extract as structuring with near-perfect similarity."""
    from app.engines.archetype_extractor import extract_archetype
    seed = get_seed("structuring")
    res = extract_archetype(seed)
    assert res["archetype"] == "structuring", f"Expected structuring, got {res['archetype']}"
    assert res["similarity"] > 0.7, f"Expected similarity > 0.7, got {res['similarity']}"
