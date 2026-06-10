"""
Tests — TGEP Webhook Contract (ISSUE 1 + 7)
=============================================
Contract tests verifying:
- report dict produced by _build_report_for_tgep contains all required fields
- fire_tgep_webhook is called only for HIGH/CRITICAL + recommended_action=PATCH
- fire_tgep_webhook is NOT called for LOW/MEDIUM severity
- maybe_fire_tgep_for_report respects the same gate
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from app.ingest.router import reset_state, _ingest_log
from app.knowledge.kb_store import append_evasion, reset_kb, get_all_evasions
from app.worker.pipeline import _build_report_for_tgep


@pytest.fixture(autouse=True)
def clean_state():
    reset_state()
    reset_kb()
    yield
    reset_state()
    reset_kb()


def _seed_evasion_for_ingest(
    ingest_id: str,
    severity: str,
    evasion_success: bool = True,
    gate: str = "cycle",
) -> str:
    return append_evasion({
        "archetype": "structuring",
        "evasion_vector": {"burst_score": 0.4},
        "gate_bypassed": [gate],
        "feature_deltas": {},
        "context_multiplier_abused": None,
        "evasion_success": evasion_success,
        "score_original": 0.88,
        "score_mutated": 0.55,
        "ingest_log_id": ingest_id,
        "mutation_type": "velocity_20pct",
        "gate_probe_result": None,
        "feature_sensitivity_result": None,
        "context_bypass_result": None,
        "severity": severity,
    })


# ─────────────────────────────────────────────────────────────────────────────
# ISSUE 1 — _build_report_for_tgep shape
# ─────────────────────────────────────────────────────────────────────────────


class TestBuildReportForTgep:
    def test_report_has_required_top_level_keys(self):
        ingest_id = "RPT-001"
        _seed_evasion_for_ingest(ingest_id, "HIGH")
        report = _build_report_for_tgep(ingest_id, "structuring", ["ev-1"])
        for key in ("id", "severity", "recommended_action", "created_at", "payload"):
            assert key in report, f"Missing top-level key: {key}"

    def test_payload_has_required_keys(self):
        ingest_id = "RPT-002"
        _seed_evasion_for_ingest(ingest_id, "HIGH")
        report = _build_report_for_tgep(ingest_id, "structuring", ["ev-1"])
        payload = report["payload"]
        for key in ("archetype", "evasions_found", "gate_vulnerabilities", "ingest_id"):
            assert key in payload, f"Missing payload key: {key}"

    def test_severity_derived_from_kb_high(self):
        ingest_id = "RPT-003"
        _seed_evasion_for_ingest(ingest_id, "HIGH")
        report = _build_report_for_tgep(ingest_id, "structuring", [])
        assert report["severity"] == "HIGH"

    def test_severity_derived_from_kb_critical(self):
        ingest_id = "RPT-004"
        _seed_evasion_for_ingest(ingest_id, "CRITICAL")
        report = _build_report_for_tgep(ingest_id, "structuring", [])
        assert report["severity"] == "CRITICAL"

    def test_severity_derived_from_kb_medium(self):
        ingest_id = "RPT-005"
        _seed_evasion_for_ingest(ingest_id, "MEDIUM")
        report = _build_report_for_tgep(ingest_id, "structuring", [])
        assert report["severity"] == "MEDIUM"

    def test_recommended_action_patch_for_high(self):
        ingest_id = "RPT-006"
        _seed_evasion_for_ingest(ingest_id, "HIGH")
        report = _build_report_for_tgep(ingest_id, "structuring", [])
        assert report["recommended_action"] == "PATCH"

    def test_recommended_action_patch_for_critical(self):
        ingest_id = "RPT-007"
        _seed_evasion_for_ingest(ingest_id, "CRITICAL")
        report = _build_report_for_tgep(ingest_id, "structuring", [])
        assert report["recommended_action"] == "PATCH"

    def test_recommended_action_monitor_for_medium(self):
        ingest_id = "RPT-008"
        _seed_evasion_for_ingest(ingest_id, "MEDIUM")
        report = _build_report_for_tgep(ingest_id, "structuring", [])
        assert report["recommended_action"] == "MONITOR"

    def test_recommended_action_accept_for_low(self):
        ingest_id = "RPT-009"
        _seed_evasion_for_ingest(ingest_id, "LOW")
        report = _build_report_for_tgep(ingest_id, "structuring", [])
        assert report["recommended_action"] == "ACCEPT"

    def test_gate_vulnerabilities_populated(self):
        ingest_id = "RPT-010"
        _seed_evasion_for_ingest(ingest_id, "HIGH", gate="cycle")
        _seed_evasion_for_ingest(ingest_id, "HIGH", gate="sink")
        report = _build_report_for_tgep(ingest_id, "structuring", [])
        gates = report["payload"]["gate_vulnerabilities"]
        assert "cycle" in gates
        assert "sink" in gates

    def test_archetype_passed_through(self):
        ingest_id = "RPT-011"
        _seed_evasion_for_ingest(ingest_id, "HIGH")
        report = _build_report_for_tgep(ingest_id, "digital_arrest", [])
        assert report["payload"]["archetype"] == "digital_arrest"

    def test_evasions_found_is_kb_count(self):
        ingest_id = "RPT-012"
        _seed_evasion_for_ingest(ingest_id, "HIGH")
        _seed_evasion_for_ingest(ingest_id, "HIGH")
        report = _build_report_for_tgep(ingest_id, "structuring", [])
        assert report["payload"]["evasions_found"] == 2

    def test_empty_kb_gives_none_severity(self):
        ingest_id = "RPT-013"
        # No KB rows for this ingest
        report = _build_report_for_tgep(ingest_id, "structuring", [])
        assert report["severity"] == "NONE"
        assert report["recommended_action"] == "ACCEPT"


# ─────────────────────────────────────────────────────────────────────────────
# ISSUE 7 — maybe_fire_tgep_for_report fires only for HIGH/CRITICAL + PATCH
# ─────────────────────────────────────────────────────────────────────────────


class TestMaybeFirTgepContract:
    @pytest.mark.asyncio
    async def test_fires_for_critical_patch(self):
        """fire_tgep_webhook must be called when severity=CRITICAL + PATCH."""
        from app.api.tgep_webhook import maybe_fire_tgep_for_report
        report = {
            "id": "rpt-c1",
            "severity": "CRITICAL",
            "recommended_action": "PATCH",
            "created_at": "2026-06-06T00:00:00Z",
            "payload": {
                "archetype": "structuring",
                "evasions_found": 3,
                "gate_vulnerabilities": ["cycle"],
                "gate_vulnerability": "cycle",
            },
        }
        with patch(
            "app.api.tgep_webhook.fire_tgep_webhook",
            new_callable=AsyncMock,
            return_value={},
        ) as mock_fire:
            result = await maybe_fire_tgep_for_report(report)
            mock_fire.assert_called_once()

    @pytest.mark.asyncio
    async def test_fires_for_high_patch(self):
        """fire_tgep_webhook must be called when severity=HIGH + PATCH."""
        from app.api.tgep_webhook import maybe_fire_tgep_for_report
        report = {
            "id": "rpt-h1",
            "severity": "HIGH",
            "recommended_action": "PATCH",
            "created_at": "2026-06-06T00:00:00Z",
            "payload": {
                "archetype": "otp_fraud",
                "evasions_found": 2,
                "gate_vulnerabilities": ["sink"],
                "gate_vulnerability": "sink",
            },
        }
        with patch(
            "app.api.tgep_webhook.fire_tgep_webhook",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_fire:
            await maybe_fire_tgep_for_report(report)
            mock_fire.assert_called_once()

    @pytest.mark.asyncio
    async def test_does_not_fire_for_medium(self):
        """fire_tgep_webhook must NOT be called for MEDIUM severity."""
        from app.api.tgep_webhook import maybe_fire_tgep_for_report
        report = {
            "id": "rpt-m1",
            "severity": "MEDIUM",
            "recommended_action": "MONITOR",
            "created_at": "2026-06-06T00:00:00Z",
            "payload": {"archetype": "structuring", "evasions_found": 1,
                        "gate_vulnerabilities": [], "gate_vulnerability": None},
        }
        with patch(
            "app.api.tgep_webhook.fire_tgep_webhook",
            new_callable=AsyncMock,
        ) as mock_fire:
            result = await maybe_fire_tgep_for_report(report)
            mock_fire.assert_not_called()
            assert result is None

    @pytest.mark.asyncio
    async def test_does_not_fire_for_low(self):
        """fire_tgep_webhook must NOT be called for LOW severity."""
        from app.api.tgep_webhook import maybe_fire_tgep_for_report
        report = {
            "id": "rpt-l1",
            "severity": "LOW",
            "recommended_action": "ACCEPT",
            "created_at": "2026-06-06T00:00:00Z",
            "payload": {"archetype": "structuring", "evasions_found": 1,
                        "gate_vulnerabilities": [], "gate_vulnerability": None},
        }
        with patch(
            "app.api.tgep_webhook.fire_tgep_webhook",
            new_callable=AsyncMock,
        ) as mock_fire:
            result = await maybe_fire_tgep_for_report(report)
            mock_fire.assert_not_called()
            assert result is None

    @pytest.mark.asyncio
    async def test_does_not_fire_when_accept_action(self):
        """fire_tgep_webhook must NOT be called when recommended_action=ACCEPT even for HIGH."""
        from app.api.tgep_webhook import maybe_fire_tgep_for_report
        report = {
            "id": "rpt-a1",
            "severity": "HIGH",
            "recommended_action": "ACCEPT",
            "created_at": "2026-06-06T00:00:00Z",
            "payload": {"archetype": "structuring", "evasions_found": 1,
                        "gate_vulnerabilities": [], "gate_vulnerability": None},
        }
        with patch(
            "app.api.tgep_webhook.fire_tgep_webhook",
            new_callable=AsyncMock,
        ) as mock_fire:
            result = await maybe_fire_tgep_for_report(report)
            mock_fire.assert_not_called()
            assert result is None

    @pytest.mark.asyncio
    async def test_fire_tgep_skips_low_severity_directly(self):
        """fire_tgep_webhook itself must return False for LOW without firing HTTP."""
        from app.api.tgep_webhook import fire_tgep_webhook
        with patch("app.api.tgep_webhook.httpx.AsyncClient") as mock_client:
            result = await fire_tgep_webhook(
                report_id="rpt-low",
                archetype="structuring",
                gate_vulnerability=None,
                proposed_patch_summary="test",
                severity="LOW",
                recommended_action="ACCEPT",
            )
            assert result is None
            mock_client.assert_not_called()

    @pytest.mark.asyncio
    async def test_fire_tgep_skips_medium_severity_directly(self):
        """fire_tgep_webhook itself must return False for MEDIUM without firing HTTP."""
        from app.api.tgep_webhook import fire_tgep_webhook
        with patch("app.api.tgep_webhook.httpx.AsyncClient") as mock_client:
            result = await fire_tgep_webhook(
                report_id="rpt-med",
                archetype="structuring",
                gate_vulnerability=None,
                proposed_patch_summary="test",
                severity="MEDIUM",
                recommended_action="MONITOR",
            )
            assert result is None
            mock_client.assert_not_called()
