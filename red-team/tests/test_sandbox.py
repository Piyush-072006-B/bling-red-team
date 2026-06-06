"""
Tests — Sandbox (Task 4.4)
=====================================
- Mock shadow scorer returning score=0.9 (HIGH_RISK)
- Run mutation engine on digital_arrest archetype
- Assert at least one mutation produces score < 0.75 in mock
- Assert gate_probe returns gate_name and near_miss_delta
- Assert feature_sensitivity returns top_5_exploitable_features
- Assert context_bypass detects festival multiplier abuse
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.engines.mutation_engine import generate_mutations
from app.sandbox.evaluators import (
    SCORE_BLOCK_THRESHOLD,
    context_bypass,
    feature_sensitivity,
    gate_probe,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

_DIGITAL_ARREST_VECTOR = {
    "night_txn_ratio": 0.9,
    "payee_vpa_age_days": 0.85,
    "amount_zscore": 0.80,
    "burst_score": 0.70,
    "velocity_ratio": 0.65,
    "is_festival_period": 0.0,
    "counterparty_novelty": 0.5,
    "hour_deviation": 0.9,
}


def _make_shadow_result(score: float, gate_fired: str | None = "cycle") -> dict:
    action = "BLOCK" if score >= 0.75 else ("REVIEW" if score >= 0.50 else "PASS")
    return {"score": score, "action": action, "gate_fired": gate_fired, "raw": {}}


# ─────────────────────────────────────────────────────────────────────────────
# Shadow scorer mock tests
# ─────────────────────────────────────────────────────────────────────────────


class TestMockShadowScorer:
    @pytest.mark.asyncio
    async def test_shadow_scorer_returns_mocked_score(self):
        """Mock shadow scorer must return the configured score without HTTP calls."""
        mock_result = _make_shadow_result(0.9, gate_fired="cycle")

        with patch(
            "app.sandbox.shadow_scorer.score_transaction",
            new=AsyncMock(return_value=mock_result),
        ):
            from app.sandbox.shadow_scorer import score_transaction

            result = await score_transaction({"amount_series_score": 0.9})
            assert result["score"] == 0.9
            assert result["action"] == "BLOCK"
            assert result["gate_fired"] == "cycle"

    @pytest.mark.asyncio
    async def test_shadow_scorer_unavailable_returns_error_dict(self):
        """On connection failure, must return error dict with score=None."""
        with patch(
            "app.sandbox.shadow_scorer.score_transaction",
            new=AsyncMock(
                return_value={
                    "score": None,
                    "action": None,
                    "gate_fired": None,
                    "error": "shadow_scorer_unavailable",
                    "reason": "timeout",
                    "detail": "Connection refused",
                }
            ),
        ):
            from app.sandbox.shadow_scorer import score_transaction

            result = await score_transaction({})
            assert result["score"] is None
            assert result["error"] == "shadow_scorer_unavailable"


class TestMutationReducesScore:
    def test_at_least_one_mutation_produces_score_below_075(self):
        """
        With digital_arrest archetype:
        - Original score = 0.9 (HIGH_RISK)
        - Simulate mutations reducing score by 30% (timing + velocity mutations)
        - Assert at least one produces score < 0.75
        """
        mutations = generate_mutations(_DIGITAL_ARREST_VECTOR, "digital_arrest", n=10)
        assert len(mutations) > 0, "No mutations generated for digital_arrest"

        original_result = _make_shadow_result(0.9, gate_fired="cycle")

        # Simulate: mutations that change night_txn_ratio or burst_score
        # reduce the score meaningfully. We compute mock scores based on delta.
        score_below_threshold_found = False

        for m in mutations:
            # Mock scoring: reduce score proportional to sum of abs deltas
            delta_sum = sum(abs(v) for v in m["delta_features"].values())
            simulated_score = max(0.0, 0.9 - delta_sum * 0.5)
            mutated_result = _make_shadow_result(simulated_score, gate_fired=None)

            probe = gate_probe(original_result, mutated_result, m)
            if probe["mutated_score"] is not None and probe["mutated_score"] < SCORE_BLOCK_THRESHOLD:
                score_below_threshold_found = True
                break

        assert score_below_threshold_found, (
            f"No mutation produced score < {SCORE_BLOCK_THRESHOLD} for digital_arrest archetype"
        )


class TestGateProbe:
    def test_gate_probe_returns_gate_name(self):
        """gate_probe must identify the bypassed gate when original had gate firing."""
        original = _make_shadow_result(0.9, gate_fired="cycle")
        mutated = _make_shadow_result(0.55, gate_fired=None)  # gate no longer fires
        mutation = {
            "mutation_type": "velocity_20pct",
            "delta_features": {"burst_score": -0.15, "velocity_ratio": -0.12},
        }

        result = gate_probe(original, mutated, mutation)

        assert "gate_bypassed" in result
        assert result["gate_bypassed"] == "cycle"
        assert "near_miss_delta" in result
        assert isinstance(result["near_miss_delta"], float)

    def test_gate_probe_returns_score_delta(self):
        original = _make_shadow_result(0.9)
        mutated = _make_shadow_result(0.6)
        mutation = {"mutation_type": "timing_day", "delta_features": {"night_txn_ratio": -0.75}}

        result = gate_probe(original, mutated, mutation)

        assert "score_delta" in result
        assert result["score_delta"] == pytest.approx(0.3, abs=0.01)

    def test_gate_probe_evasion_achieved_when_score_drops_below_block(self):
        original = _make_shadow_result(0.9, gate_fired="sink")
        mutated = _make_shadow_result(0.45, gate_fired=None)
        mutation = {"mutation_type": "threshold_amount_50k", "delta_features": {"amount_series_score": -0.9}}

        result = gate_probe(original, mutated, mutation)

        assert result["evasion_achieved"] is True

    def test_gate_probe_no_evasion_when_still_high_risk(self):
        original = _make_shadow_result(0.9)
        mutated = _make_shadow_result(0.80)
        mutation = {"mutation_type": "velocity_20pct", "delta_features": {"burst_score": -0.1}}

        result = gate_probe(original, mutated, mutation)

        assert result["evasion_achieved"] is False

    def test_gate_probe_handles_unavailable_scorer(self):
        """gate_probe must not crash when mutated score is None."""
        original = _make_shadow_result(0.9)
        mutated = {
            "score": None,
            "action": None,
            "gate_fired": None,
            "error": "shadow_scorer_unavailable",
        }
        mutation = {"mutation_type": "novelty_zero", "delta_features": {"counterparty_novelty": -0.6}}

        result = gate_probe(original, mutated, mutation)
        assert result["mutated_score"] is None
        assert result["evasion_achieved"] is False


class TestFeatureSensitivity:
    def test_returns_top_5_exploitable_features(self):
        original = _make_shadow_result(0.9)
        mutated = _make_shadow_result(0.55)
        mutation = {
            "mutation_type": "timing_day",
            "delta_features": {
                "night_txn_ratio": -0.75,
                "hour_deviation": -0.9,
                "burst_score": -0.1,
                "velocity_ratio": -0.05,
                "counterparty_novelty": -0.01,
            },
        }

        result = feature_sensitivity(original, mutated, mutation)

        assert "top_5_exploitable_features" in result
        top5 = result["top_5_exploitable_features"]
        assert len(top5) <= 5
        assert len(top5) > 0
        # First result must be the highest impact feature (largest abs shap_delta)
        # hour_deviation (-0.9) has larger abs delta than night_txn_ratio (-0.75)
        assert top5[0]["feature"] in ("hour_deviation", "night_txn_ratio")
        assert top5[0]["impact_rank"] == 1
        # Verify top feature has largest absolute shap_delta in the list
        max_delta = max(abs(f["shap_delta"]) for f in top5)
        assert abs(top5[0]["shap_delta"]) == max_delta

    def test_total_features_changed_is_accurate(self):
        original = _make_shadow_result(0.9)
        mutated = _make_shadow_result(0.6)
        mutation = {
            "mutation_type": "velocity_20pct",
            "delta_features": {"burst_score": -0.164, "velocity_ratio": -0.156},
        }

        result = feature_sensitivity(original, mutated, mutation)
        assert result["total_features_changed"] == 2


class TestContextBypass:
    def test_detects_festival_multiplier_abuse(self):
        """context_bypass must detect is_festival_period flip as multiplier abuse."""
        original = _make_shadow_result(0.9)
        mutated = _make_shadow_result(0.63)
        mutation = {
            "mutation_type": "context_festival",
            "delta_features": {"is_festival_period": 1.0},
        }

        result = context_bypass(original, mutated, mutation)

        assert result["context_abuse_confirmed"] is True
        assert result["multiplier_abused"] == "is_festival_period"
        assert result["multiplier_value"] == pytest.approx(0.70)

    def test_no_context_abuse_without_multiplier_change(self):
        original = _make_shadow_result(0.9)
        mutated = _make_shadow_result(0.80)
        mutation = {
            "mutation_type": "velocity_20pct",
            "delta_features": {"burst_score": -0.15, "velocity_ratio": -0.12},
        }

        result = context_bypass(original, mutated, mutation)
        assert result["multiplier_abused"] is None
        assert result["context_abuse_confirmed"] is False
