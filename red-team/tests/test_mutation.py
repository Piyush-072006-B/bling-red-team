"""
Tests — Mutation Engine (Task 4.2)
=====================================
- test_generates_10_mutations: assert 10 mutations for structuring archetype
- test_threshold_mutations_below_50000: threshold mutations produce amounts < 1.0 score (proxy)
- test_mutated_differs_from_original: mutated_vector != original_vector for all mutations
- test_all_mutations_have_required_keys: each mutation has all required fields
- test_velocity_mutations_reduce_score: velocity features are reduced after velocity mutations
"""

from __future__ import annotations

import pytest

from app.engines.mutation_engine import generate_mutations


_STRUCTURING_VECTOR = {
    "amount_series_score": 0.95,
    "txn_count_30d": 0.85,
    "amount_vs_threshold_50000": 0.98,
    "amount_vs_threshold_100000": 0.7,
    "amount_vs_threshold_1000000": 0.3,
    "burst_score": 0.82,
    "velocity_ratio": 0.78,
    "night_txn_ratio": 0.65,
    "hour_deviation": 0.8,
    "is_festival_period": 0.0,
    "counterparty_novelty": 0.6,
    "return_ratio": 0.4,
}

_DIGITAL_ARREST_VECTOR = {
    "night_txn_ratio": 0.9,
    "payee_vpa_age_days": 0.8,
    "amount_zscore": 0.75,
    "burst_score": 0.6,
    "velocity_ratio": 0.5,
    "is_festival_period": 0.0,
    "counterparty_novelty": 0.4,
}

_REQUIRED_KEYS = {
    "mutation_id",
    "mutation_type",
    "delta_features",
    "original_vector",
    "mutated_vector",
}


class TestMutationGeneration:
    def test_generates_16_mutations_structuring(self):
        """Structuring archetype must produce exactly 16 mutations."""
        mutations = generate_mutations(_STRUCTURING_VECTOR, "structuring", n=16)
        assert len(mutations) == 16, (
            f"Expected 16 mutations, got {len(mutations)}: "
            f"{[m['mutation_type'] for m in mutations]}"
        )

    def test_all_mutations_have_required_keys(self):
        mutations = generate_mutations(_STRUCTURING_VECTOR, "structuring", n=16)
        for m in mutations:
            missing = _REQUIRED_KEYS - set(m.keys())
            assert not missing, f"Mutation missing keys {missing}: {m}"

    def test_mutation_ids_are_unique(self):
        mutations = generate_mutations(_STRUCTURING_VECTOR, "structuring", n=16)
        ids = [m["mutation_id"] for m in mutations]
        assert len(ids) == len(set(ids)), "Mutation IDs are not unique"

    def test_threshold_mutations_reduce_score(self):
        """Threshold mutations must reduce amount_series_score below original."""
        mutations = generate_mutations(_STRUCTURING_VECTOR, "structuring", n=16)
        threshold_muts = [m for m in mutations if "threshold" in m["mutation_type"]]
        assert len(threshold_muts) > 0, "No threshold mutations generated"

        for m in threshold_muts:
            orig = m["original_vector"].get("amount_series_score", 0)
            mutd = m["mutated_vector"].get("amount_series_score", orig)
            assert mutd <= orig, (
                f"threshold mutation '{m['mutation_type']}' did not reduce "
                f"amount_series_score: {orig} → {mutd}"
            )

    def test_mutated_vector_differs_from_original(self):
        """Every mutation must produce a vector different from the original."""
        mutations = generate_mutations(_STRUCTURING_VECTOR, "structuring", n=16)
        for m in mutations:
            assert m["mutated_vector"] != m["original_vector"], (
                f"Mutation '{m['mutation_type']}' produced identical vector"
            )

    def test_delta_features_not_empty(self):
        """Every mutation must have at least one delta feature."""
        mutations = generate_mutations(_STRUCTURING_VECTOR, "structuring", n=16)
        for m in mutations:
            assert m["delta_features"], (
                f"Mutation '{m['mutation_type']}' has empty delta_features"
            )

    def test_velocity_mutations_reduce_burst_score(self):
        """Velocity mutations must reduce burst_score."""
        mutations = generate_mutations(_STRUCTURING_VECTOR, "structuring", n=16)
        velocity_muts = [m for m in mutations if "velocity" in m["mutation_type"]]
        assert len(velocity_muts) > 0, "No velocity mutations generated"
        for m in velocity_muts:
            orig = m["original_vector"].get("burst_score", 0)
            mutd = m["mutated_vector"].get("burst_score", orig)
            assert mutd < orig, (
                f"velocity mutation '{m['mutation_type']}' did not reduce burst_score: "
                f"{orig} → {mutd}"
            )

    def test_timing_mutation_pushes_night_ratio_to_015(self):
        """Timing mutation must set night_txn_ratio ≤ 0.15."""
        mutations = generate_mutations(_STRUCTURING_VECTOR, "structuring", n=16)
        timing_muts = [m for m in mutations if m["mutation_type"] == "timing_day"]
        assert len(timing_muts) > 0, "No timing mutation generated"
        m = timing_muts[0]
        assert m["mutated_vector"]["night_txn_ratio"] <= 0.15

    def test_novelty_zero_mutation_sets_counterparty_to_zero(self):
        mutations = generate_mutations(_STRUCTURING_VECTOR, "structuring", n=16)
        novelty_muts = [m for m in mutations if m["mutation_type"] == "novelty_zero"]
        assert len(novelty_muts) > 0, "No novelty_zero mutation generated"
        assert novelty_muts[0]["mutated_vector"]["counterparty_novelty"] == 0.0

    def test_context_festival_mutation_flips_flag(self):
        mutations = generate_mutations(_STRUCTURING_VECTOR, "structuring", n=16)
        festival_muts = [m for m in mutations if m["mutation_type"] == "context_festival"]
        assert len(festival_muts) > 0, "No context_festival mutation generated"
        assert festival_muts[0]["mutated_vector"]["is_festival_period"] == 1.0

    def test_original_vector_is_not_mutated_in_place(self):
        """The original feature_vector dict must not be modified by generate_mutations."""
        vec = dict(_STRUCTURING_VECTOR)
        original_copy = dict(vec)
        generate_mutations(vec, "structuring", n=16)
        assert vec == original_copy, "Original vector was mutated in place!"

    def test_digital_arrest_archetype_produces_mutations(self):
        mutations = generate_mutations(_DIGITAL_ARREST_VECTOR, "digital_arrest", n=16)
        assert len(mutations) >= 5, f"Expected at least 5 mutations, got {len(mutations)}"

    def test_threshold_amount_50k_feature_below_original(self):
        """50k threshold mutation must reduce the amount_vs_threshold_50000 score."""
        mutations = generate_mutations(_STRUCTURING_VECTOR, "structuring", n=16)
        t50k = [m for m in mutations if m["mutation_type"] == "threshold_amount_50k"]
        if t50k:
            orig = t50k[0]["original_vector"].get("amount_vs_threshold_50000", 1.0)
            mutd = t50k[0]["mutated_vector"].get("amount_vs_threshold_50000", 1.0)
            assert mutd < orig, f"50k threshold not reduced: {orig} → {mutd}"

    def test_compound_festival_layering_changes_4_features(self):
        mutations = generate_mutations(_STRUCTURING_VECTOR, "structuring", n=16)
        cfl = [m for m in mutations if m["mutation_type"] == "compound_festival_layering"]
        assert len(cfl) > 0, "compound_festival_layering mutation not found"
        assert len(cfl[0]["delta_features"]) >= 4, "Should change at least 4 features"

    def test_compound_mutations_included_and_correct_features(self):
        mutations = generate_mutations(_STRUCTURING_VECTOR, "structuring", n=16)
        types = [m["mutation_type"] for m in mutations]
        expected_compound = [
            "compound_daytime_slowdown",
            "compound_structuring_ghost",
            "compound_festival_layering",
            "compound_mule_warmup",
            "compound_kyc_ghost",
            "compound_senior_festival_night"
        ]
        for c in expected_compound:
            assert c in types, f"Missing {c} in mutations"
            
        ghost = next(m for m in mutations if m["mutation_type"] == "compound_structuring_ghost")
        assert set(ghost["delta_features"].keys()).issubset({
            "amount_series_score", "amount_vs_threshold_50000", "counterparty_novelty", "txn_count_30d"
        })
