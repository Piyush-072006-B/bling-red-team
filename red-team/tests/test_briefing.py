"""
Tests — GET /red-team/briefing (Task: Briefing Endpoint)
==========================================================
- Empty KB returns valid structure with zero counts and empty lists
- Mixed severity KB (CRITICAL/HIGH/MEDIUM/LOW) returns correct grouping
- CRITICAL evasion_success=False goes to 'structural_findings', not 'immediate_action_required'
- Duplicate mutation types are merged into a single BriefingItem
- top_exploitable_features reflects feature frequency across feature_sensitivity_results
- context_multipliers_at_risk includes abused multipliers
- Endpoint is auth-protected (403 without key)
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.ingest.router import reset_state
from app.knowledge.kb_store import append_evasion, reset_kb


@pytest.fixture(autouse=True)
def clean_state():
    reset_state()
    reset_kb()
    yield
    reset_state()
    reset_kb()


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app, raise_server_exceptions=True)


_HEADERS = {"X-API-Key": "changeme"}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers to seed the KB
# ─────────────────────────────────────────────────────────────────────────────


def _seed_evasion(
    severity: str = "HIGH",
    evasion_success: bool = True,
    mutation_type: str = "velocity_20pct",
    context_multiplier_abused: str | None = None,
    feature_sensitivity_result: dict | None = None,
) -> str:
    return append_evasion({
        "archetype": "structuring",
        "evasion_vector": {"burst_score": 0.4},
        "gate_bypassed": ["cycle"],
        "feature_deltas": {"burst_score": -0.2},
        "context_multiplier_abused": context_multiplier_abused,
        "evasion_success": evasion_success,
        "score_original": 0.88,
        "score_mutated": 0.60,
        "ingest_log_id": "TEST-INGEST",
        "mutation_type": mutation_type,
        "gate_probe_result": None,
        "feature_sensitivity_result": feature_sensitivity_result,
        "context_bypass_result": None,
        "severity": severity,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Empty KB
# ─────────────────────────────────────────────────────────────────────────────


class TestEmptyKB:
    def test_returns_200(self, client):
        r = client.get("/red-team/briefing", headers=_HEADERS)
        assert r.status_code == 200

    def test_has_all_required_keys(self, client):
        r = client.get("/red-team/briefing", headers=_HEADERS)
        body = r.json()
        assert "generated_at" in body
        assert "threat_summary" in body
        assert "immediate_action_required" in body
        assert "monitor" in body
        assert "structural_findings" in body
        assert "top_exploitable_features" in body
        assert "context_multipliers_at_risk" in body

    def test_empty_kb_zero_counts(self, client):
        r = client.get("/red-team/briefing", headers=_HEADERS)
        body = r.json()
        assert body["immediate_action_required"] == []
        assert body["monitor"] == []
        assert body["structural_findings"] == []
        assert body["top_exploitable_features"] == []
        assert body["context_multipliers_at_risk"] == []

    def test_empty_kb_threat_summary(self, client):
        r = client.get("/red-team/briefing", headers=_HEADERS)
        body = r.json()
        assert "0 active evasion" in body["threat_summary"]
        assert "0 CRITICAL" in body["threat_summary"]
        assert "0 HIGH" in body["threat_summary"]

    def test_auth_required(self, client):
        r = client.get("/red-team/briefing")
        assert r.status_code == 403


# ─────────────────────────────────────────────────────────────────────────────
# Mixed severity KB — grouping
# ─────────────────────────────────────────────────────────────────────────────


class TestMixedSeverityGrouping:
    def test_critical_success_goes_to_immediate(self, client):
        _seed_evasion(severity="CRITICAL", evasion_success=True, mutation_type="graph_bypass_cycle")
        r = client.get("/red-team/briefing", headers=_HEADERS)
        body = r.json()
        assert len(body["immediate_action_required"]) == 1
        assert len(body["monitor"]) == 0

    def test_critical_no_success_goes_to_structural_findings(self, client):
        """CRITICAL severity but evasion_success=False -> structural_findings, not immediate."""
        _seed_evasion(severity="CRITICAL", evasion_success=False, mutation_type="timing_day")
        r = client.get("/red-team/briefing", headers=_HEADERS)
        body = r.json()
        assert len(body["immediate_action_required"]) == 0
        assert len(body["structural_findings"]) == 1

    def test_high_goes_to_monitor(self, client):
        _seed_evasion(severity="HIGH", evasion_success=True, mutation_type="velocity_20pct")
        r = client.get("/red-team/briefing", headers=_HEADERS)
        body = r.json()
        assert len(body["monitor"]) == 1
        assert len(body["immediate_action_required"]) == 0

    def test_medium_goes_to_structural_findings(self, client):
        _seed_evasion(severity="MEDIUM", evasion_success=False, mutation_type="novelty_zero")
        r = client.get("/red-team/briefing", headers=_HEADERS)
        body = r.json()
        assert len(body["structural_findings"]) == 1
        assert len(body["monitor"]) == 0

    def test_low_goes_to_structural_findings(self, client):
        _seed_evasion(severity="LOW", evasion_success=False, mutation_type="context_festival")
        r = client.get("/red-team/briefing", headers=_HEADERS)
        body = r.json()
        assert len(body["structural_findings"]) == 1

    def test_mixed_severity_correct_counts(self, client):
        """Seed one of each severity and verify correct bucketing."""
        _seed_evasion(severity="CRITICAL", evasion_success=True,  mutation_type="graph_bypass_cycle")
        _seed_evasion(severity="CRITICAL", evasion_success=True,  mutation_type="graph_bypass_sink")
        _seed_evasion(severity="HIGH",     evasion_success=True,  mutation_type="velocity_20pct")
        _seed_evasion(severity="MEDIUM",   evasion_success=False, mutation_type="timing_day")
        _seed_evasion(severity="LOW",      evasion_success=False, mutation_type="novelty_zero")

        r = client.get("/red-team/briefing", headers=_HEADERS)
        body = r.json()

        assert len(body["immediate_action_required"]) == 2
        assert len(body["monitor"]) == 1
        assert len(body["structural_findings"]) == 2

    def test_threat_summary_counts_match(self, client):
        """threat_summary string reflects the actual item counts."""
        _seed_evasion(severity="CRITICAL", evasion_success=True,  mutation_type="graph_bypass_cycle")
        _seed_evasion(severity="HIGH",     evasion_success=True,  mutation_type="velocity_20pct")

        r = client.get("/red-team/briefing", headers=_HEADERS)
        body = r.json()

        assert "1 CRITICAL" in body["threat_summary"]
        assert "1 HIGH" in body["threat_summary"]


# ─────────────────────────────────────────────────────────────────────────────
# BriefingItem structure
# ─────────────────────────────────────────────────────────────────────────────


class TestBriefingItemStructure:
    def test_immediate_item_has_required_keys(self, client):
        _seed_evasion(severity="CRITICAL", evasion_success=True, mutation_type="graph_bypass_cycle")
        r = client.get("/red-team/briefing", headers=_HEADERS)
        item = r.json()["immediate_action_required"][0]
        for key in ("priority", "severity", "title", "what_was_found", "what_to_change", "file", "evasion_ids"):
            assert key in item, f"Missing key: {key}"

    def test_evasion_ids_is_list(self, client):
        _seed_evasion(severity="CRITICAL", evasion_success=True, mutation_type="graph_bypass_cycle")
        r = client.get("/red-team/briefing", headers=_HEADERS)
        item = r.json()["immediate_action_required"][0]
        assert isinstance(item["evasion_ids"], list)
        assert len(item["evasion_ids"]) == 1

    def test_duplicate_mutation_types_merged(self, client):
        """Two HIGH evasions with the same mutation_type should merge into one item."""
        _seed_evasion(severity="HIGH", evasion_success=True, mutation_type="velocity_20pct")
        _seed_evasion(severity="HIGH", evasion_success=True, mutation_type="velocity_20pct")
        r = client.get("/red-team/briefing", headers=_HEADERS)
        body = r.json()
        assert len(body["monitor"]) == 1
        assert len(body["monitor"][0]["evasion_ids"]) == 2

    def test_priority_starts_at_1(self, client):
        _seed_evasion(severity="CRITICAL", evasion_success=True, mutation_type="graph_bypass_cycle")
        r = client.get("/red-team/briefing", headers=_HEADERS)
        item = r.json()["immediate_action_required"][0]
        assert item["priority"] == 1


# ─────────────────────────────────────────────────────────────────────────────
# Top exploitable features
# ─────────────────────────────────────────────────────────────────────────────


class TestTopExploitableFeatures:
    def test_top_features_from_feature_sensitivity(self, client):
        """Features mentioned in feature_sensitivity_result should appear in top_exploitable_features."""
        fs = {
            "top_5_exploitable_features": [
                {"feature": "burst_score", "shap_delta": 0.3, "delta_value": -0.2, "impact_rank": 1},
                {"feature": "velocity_ratio", "shap_delta": 0.2, "delta_value": -0.1, "impact_rank": 2},
            ],
            "total_features_changed": 2,
            "score_delta": 0.25,
            "shap_available": False,
        }
        _seed_evasion(severity="HIGH", evasion_success=True, feature_sensitivity_result=fs)
        r = client.get("/red-team/briefing", headers=_HEADERS)
        top = r.json()["top_exploitable_features"]
        assert "burst_score" in top
        assert "velocity_ratio" in top

    def test_top_features_capped_at_3(self, client):
        """At most 3 features returned."""
        fs = {
            "top_5_exploitable_features": [
                {"feature": f"feat_{i}", "shap_delta": 0.1, "delta_value": -0.1, "impact_rank": i}
                for i in range(1, 6)
            ],
            "total_features_changed": 5,
            "score_delta": 0.2,
            "shap_available": False,
        }
        _seed_evasion(severity="HIGH", evasion_success=True, feature_sensitivity_result=fs)
        r = client.get("/red-team/briefing", headers=_HEADERS)
        assert len(r.json()["top_exploitable_features"]) <= 3

    def test_most_frequent_feature_first(self, client):
        """Feature appearing in most evasions should rank first."""
        fs_burst = {
            "top_5_exploitable_features": [
                {"feature": "burst_score", "shap_delta": 0.3, "delta_value": -0.2, "impact_rank": 1},
            ],
            "total_features_changed": 1, "score_delta": 0.1, "shap_available": False,
        }
        fs_velocity = {
            "top_5_exploitable_features": [
                {"feature": "burst_score", "shap_delta": 0.2, "delta_value": -0.1, "impact_rank": 1},
                {"feature": "velocity_ratio", "shap_delta": 0.1, "delta_value": -0.05, "impact_rank": 2},
            ],
            "total_features_changed": 2, "score_delta": 0.15, "shap_available": False,
        }
        # burst_score appears in 2 evasions, velocity_ratio in 1
        _seed_evasion(severity="HIGH", evasion_success=True, feature_sensitivity_result=fs_burst)
        _seed_evasion(severity="HIGH", evasion_success=True, feature_sensitivity_result=fs_velocity)
        r = client.get("/red-team/briefing", headers=_HEADERS)
        top = r.json()["top_exploitable_features"]
        assert top[0] == "burst_score"


# ─────────────────────────────────────────────────────────────────────────────
# Context multipliers at risk
# ─────────────────────────────────────────────────────────────────────────────


class TestContextMultipliersAtRisk:
    def test_festival_multiplier_included(self, client):
        _seed_evasion(
            severity="CRITICAL",
            evasion_success=True,
            mutation_type="context_festival",
            context_multiplier_abused="is_festival_period",
        )
        r = client.get("/red-team/briefing", headers=_HEADERS)
        multipliers = r.json()["context_multipliers_at_risk"]
        assert "festival_0.70x" in multipliers

    def test_no_multiplier_abused_gives_empty_list(self, client):
        _seed_evasion(severity="HIGH", evasion_success=True, mutation_type="velocity_20pct")
        r = client.get("/red-team/briefing", headers=_HEADERS)
        multipliers = r.json()["context_multipliers_at_risk"]
        assert multipliers == []

    def test_duplicate_multipliers_deduplicated(self, client):
        """Same multiplier abused in two evasions should appear once."""
        _seed_evasion(severity="CRITICAL", evasion_success=True,
                      mutation_type="context_festival", context_multiplier_abused="is_festival_period")
        _seed_evasion(severity="HIGH", evasion_success=True,
                      mutation_type="context_festival", context_multiplier_abused="is_festival_period")
        r = client.get("/red-team/briefing", headers=_HEADERS)
        multipliers = r.json()["context_multipliers_at_risk"]
        assert multipliers.count("festival_0.70x") == 1


# ─────────────────────────────────────────────────────────────────────────────
# Mutation Intelligence
# ─────────────────────────────────────────────────────────────────────────────


class TestMutationIntelligence:
    def test_mutation_intelligence_present_when_all_low(self, client):
        """mutation_intelligence should be present even if all evasions are LOW severity (shadow scorer offline)."""
        _seed_evasion(severity="LOW", evasion_success=False, mutation_type="velocity_20pct")
        r = client.get("/red-team/briefing", headers=_HEADERS)
        body = r.json()
        assert "mutation_intelligence" in body
        mi = body["mutation_intelligence"]
        assert "Shadow scorer offline" in mi["summary"] or "Structural analysis" in mi["summary"]
        assert mi["mutations_generated"] >= 1

    def test_top_exploitable_features_ranked_by_times_exploited(self, client):
        fs_velocity = {
            "top_5_exploitable_features": [
                {"feature": "velocity_ratio", "shap_delta": 0.2, "delta_value": -0.1, "impact_rank": 1},
            ]
        }
        fs_burst = {
            "top_5_exploitable_features": [
                {"feature": "burst_score", "shap_delta": 0.3, "delta_value": -0.2, "impact_rank": 1},
            ]
        }
        # Seed velocity twice, burst once
        _seed_evasion(severity="LOW", feature_sensitivity_result=fs_velocity)
        _seed_evasion(severity="LOW", feature_sensitivity_result=fs_velocity)
        _seed_evasion(severity="LOW", feature_sensitivity_result=fs_burst)
        
        r = client.get("/red-team/briefing", headers=_HEADERS)
        mi = r.json()["mutation_intelligence"]
        top_features = mi["top_exploitable_features"]
        
        assert len(top_features) == 2
        assert top_features[0]["feature"] == "velocity_ratio"
        assert top_features[0]["times_exploited"] == 2
        assert top_features[1]["feature"] == "burst_score"
        assert top_features[1]["times_exploited"] == 1

    def test_context_multipliers_tested_populated(self, client):
        _seed_evasion(
            severity="LOW",
            mutation_type="context_festival",
            context_multiplier_abused="is_festival_period"
        )
        r = client.get("/red-team/briefing", headers=_HEADERS)
        mi = r.json()["mutation_intelligence"]
        multipliers = mi["context_multipliers_tested"]
        
        assert len(multipliers) == 1
        assert multipliers[0]["multiplier"] == "is_festival_period"
        assert multipliers[0]["times_tested"] == 1
        assert multipliers[0]["multiplier_value"] == 0.70
        assert "Festival period multiplier" in multipliers[0]["plain_english"]
