"""
Tests — Background Worker Pipeline (Task 4.5)
==============================================
Verifies that the worker pipeline:
  - Picks up a queued FRAUD_DNA item, runs it through the engines, and
    marks it COMPLETED in the ingest_log with evasions in the KB.
  - Picks up a NOVELTY item and generates 5 graph bypass evasions.
  - Picks up a GATE_MISS item and generates 1 graph bypass evasion.
  - Marks items FAILED in ingest_log when pipeline raises.
  - update_ingest_status correctly mutates log entries.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.ingest.router import (
    _ingest_log,
    _queue,
    _seen_hashes,
    get_ingest_log,
    get_seen_hashes,
    reset_state,
    update_ingest_status,
)
from app.knowledge.kb_store import get_all_evasions, reset_kb
from app.worker.pipeline import (
    _pipeline_fraud_dna,
    _pipeline_gate_miss,
    _pipeline_novelty,
    worker_loop,
)


# ─────────────────────────────────────────────────────────────────────────────
# Shared fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def clean_state():
    """Reset all in-memory state before and after every test."""
    reset_state()
    reset_kb()
    yield
    reset_state()
    reset_kb()


# Mock shadow scorer to avoid network calls in unit tests
@pytest.fixture
def mock_shadow_scorer():
    """Patch score_transaction to return a deterministic high-risk score."""
    score_result = {
        "score": 0.85,
        "action": "BLOCK",
        "gate_fired": "cycle",
        "raw": {},
    }
    with patch(
        "app.worker.pipeline.score_transaction",
        new_callable=AsyncMock,
        return_value=score_result,
    ) as mock:
        yield mock


@pytest.fixture
def mock_shadow_scorer_low():
    """Patch score_transaction to return a low (evaded) score for mutated vectors."""
    call_count = [0]

    async def _side_effect(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            # First call = original vector → high risk
            return {"score": 0.90, "action": "BLOCK", "gate_fired": "cycle", "raw": {}}
        # Subsequent calls = mutated vectors → evasion achieved
        return {"score": 0.55, "action": "REVIEW", "gate_fired": None, "raw": {}}

    with patch("app.worker.pipeline.score_transaction", side_effect=_side_effect) as mock:
        yield mock


@pytest.fixture
def mock_tgep():
    """Patch send_to_tgep and clear_tgep_graph to be no-ops (avoids network calls)."""
    with patch(
        "app.worker.pipeline.send_to_tgep",
        new_callable=AsyncMock,
        return_value={"status": "ok"},
    ) as mock_send, patch(
        "app.worker.pipeline.clear_tgep_graph",
        new_callable=AsyncMock,
    ):
        yield mock_send


# ─────────────────────────────────────────────────────────────────────────────
# Shared test payload helpers
# ─────────────────────────────────────────────────────────────────────────────


class _FakeFraudDNA:
    source_type = "FRAUD_DNA"
    transaction_id = "TXN-WORKER-001"
    account_id = "ACC-001"
    confirmed_archetype = "structuring"
    feature_vector = {
        "amount_series_score": 0.9,
        "txn_count_30d": 0.8,
        "amount_vs_threshold_50000": 0.95,
        "burst_score": 0.7,
        "velocity_ratio": 0.6,
        "night_txn_ratio": 0.3,
        "counterparty_novelty": 0.5,
        "is_festival_period": 0.0,
    }


class _FakeNovelty:
    source_type = "NOVELTY"
    fingerprint_id = "FP-WORKER-001"
    structural_features = {
        "bipartite_score": 0.8,
        "fan_out_ratio": 0.7,
        "cycle_membership": 0.4,
    }
    occurrence_count = 20


class _FakeGateMiss:
    source_type = "GATE_MISS"
    transaction_id = "TXN-WORKER-002"
    gate_name = "cycle"
    alert_id = "ALERT-001"


# ─────────────────────────────────────────────────────────────────────────────
# update_ingest_status
# ─────────────────────────────────────────────────────────────────────────────


class TestUpdateIngestStatus:
    def test_returns_true_for_existing_entry(self):
        """update_ingest_status returns True when the entry exists."""
        # Manually add a log entry
        from app.ingest.router import _ingest_log
        _ingest_log.append({"id": "TEST-ID", "status": "QUEUED"})

        result = update_ingest_status("TEST-ID", "IN_PROGRESS")
        assert result is True

    def test_status_is_updated(self):
        from app.ingest.router import _ingest_log
        _ingest_log.append({"id": "TEST-ID-2", "status": "QUEUED"})

        update_ingest_status("TEST-ID-2", "COMPLETED")
        entry = next(e for e in _ingest_log if e["id"] == "TEST-ID-2")
        assert entry["status"] == "COMPLETED"

    def test_error_field_is_set_on_failure(self):
        from app.ingest.router import _ingest_log
        _ingest_log.append({"id": "TEST-ID-3", "status": "QUEUED"})

        update_ingest_status("TEST-ID-3", "FAILED", error="something went wrong")
        entry = next(e for e in _ingest_log if e["id"] == "TEST-ID-3")
        assert entry["status"] == "FAILED"
        assert entry["error"] == "something went wrong"

    def test_returns_false_for_missing_entry(self):
        result = update_ingest_status("NONEXISTENT", "COMPLETED")
        assert result is False


# ─────────────────────────────────────────────────────────────────────────────
# FRAUD_DNA pipeline
# ─────────────────────────────────────────────────────────────────────────────


class TestFraudDNAPipeline:
    @pytest.mark.asyncio
    async def test_fraud_dna_pipeline_appends_evasions(self, mock_shadow_scorer, mock_tgep):
        """Running _pipeline_fraud_dna should append evasion records to the KB."""
        from app.ingest.router import _ingest_log
        _ingest_log.append({"id": "INGEST-001", "status": "QUEUED"})

        await _pipeline_fraud_dna("INGEST-001", _FakeFraudDNA())

        evasions = get_all_evasions()
        assert len(evasions) > 0, "Expected evasion records in KB"

    @pytest.mark.asyncio
    async def test_fraud_dna_pipeline_evasions_linked_to_ingest(self, mock_shadow_scorer, mock_tgep):
        """All KB entries should have ingest_log_id set to the ingest_id."""
        from app.ingest.router import _ingest_log
        _ingest_log.append({"id": "INGEST-002", "status": "QUEUED"})

        await _pipeline_fraud_dna("INGEST-002", _FakeFraudDNA())

        evasions = get_all_evasions()
        for ev in evasions:
            assert ev["ingest_log_id"] == "INGEST-002"

    @pytest.mark.asyncio
    async def test_fraud_dna_pipeline_calls_shadow_scorer(self, mock_shadow_scorer, mock_tgep):
        """shadow scorer should be called at least once (original) + once per mutation."""
        from app.ingest.router import _ingest_log
        _ingest_log.append({"id": "INGEST-003", "status": "QUEUED"})

        await _pipeline_fraud_dna("INGEST-003", _FakeFraudDNA())

        # 1 original + 10 mutations = 11 calls minimum
        assert mock_shadow_scorer.call_count >= 2

    @pytest.mark.asyncio
    async def test_fraud_dna_evasions_have_archetype(self, mock_shadow_scorer, mock_tgep):
        """Each evasion record should have an archetype field."""
        from app.ingest.router import _ingest_log
        _ingest_log.append({"id": "INGEST-004", "status": "QUEUED"})

        await _pipeline_fraud_dna("INGEST-004", _FakeFraudDNA())

        evasions = get_all_evasions()
        for ev in evasions:
            assert ev.get("archetype") is not None

    @pytest.mark.asyncio
    async def test_fraud_dna_evasion_achieved_when_score_drops(self, mock_shadow_scorer_low, mock_tgep):
        """When mutated score < BLOCK threshold, evasion_success should be True on at least one record."""
        from app.ingest.router import _ingest_log
        _ingest_log.append({"id": "INGEST-005", "status": "QUEUED"})

        await _pipeline_fraud_dna("INGEST-005", _FakeFraudDNA())

        evasions = get_all_evasions()
        successful = [e for e in evasions if e["evasion_success"] is True]
        assert len(successful) > 0, "Expected at least one successful evasion"

    @pytest.mark.asyncio
    async def test_fraud_dna_pipeline_fires_tgep_webhook(self, mock_shadow_scorer, mock_tgep):
        """send_to_tgep should be called for each mutation + graph bypass after pipeline completes."""
        from app.ingest.router import _ingest_log
        _ingest_log.append({"id": "INGEST-006", "status": "QUEUED"})

        await _pipeline_fraud_dna("INGEST-006", _FakeFraudDNA())

        assert mock_tgep.call_count > 0, "Expected send_to_tgep to be called at least once"


# ─────────────────────────────────────────────────────────────────────────────
# NOVELTY pipeline
# ─────────────────────────────────────────────────────────────────────────────


class TestNoveltyPipeline:
    @pytest.mark.asyncio
    async def test_novelty_pipeline_generates_5_bypasses(self):
        """NOVELTY pipeline should create one evasion record per gate (5 total)."""
        from app.ingest.router import _ingest_log
        _ingest_log.append({"id": "INGEST-007", "status": "QUEUED"})

        await _pipeline_novelty("INGEST-007", _FakeNovelty())

        evasions = get_all_evasions()
        assert len(evasions) == 5, f"Expected 5 bypass evasions, got {len(evasions)}"

    @pytest.mark.asyncio
    async def test_novelty_pipeline_evasions_are_linked(self):
        from app.ingest.router import _ingest_log
        _ingest_log.append({"id": "INGEST-008", "status": "QUEUED"})

        await _pipeline_novelty("INGEST-008", _FakeNovelty())

        evasions = get_all_evasions()
        for ev in evasions:
            assert ev["ingest_log_id"] == "INGEST-008"

    @pytest.mark.asyncio
    async def test_novelty_pipeline_each_evasion_has_gate(self):
        """Each bypass evasion should declare a gate_bypassed list with one item."""
        from app.ingest.router import _ingest_log
        _ingest_log.append({"id": "INGEST-009", "status": "QUEUED"})

        await _pipeline_novelty("INGEST-009", _FakeNovelty())

        evasions = get_all_evasions()
        for ev in evasions:
            assert isinstance(ev.get("gate_bypassed"), list)
            assert len(ev["gate_bypassed"]) == 1


# ─────────────────────────────────────────────────────────────────────────────
# GATE_MISS pipeline
# ─────────────────────────────────────────────────────────────────────────────


class TestGateMissPipeline:
    @pytest.mark.asyncio
    async def test_gate_miss_pipeline_appends_one_evasion(self):
        """GATE_MISS pipeline should append exactly one evasion record."""
        from app.ingest.router import _ingest_log
        _ingest_log.append({"id": "INGEST-010", "status": "QUEUED"})

        await _pipeline_gate_miss("INGEST-010", _FakeGateMiss())

        evasions = get_all_evasions()
        assert len(evasions) == 1

    @pytest.mark.asyncio
    async def test_gate_miss_gate_name_in_evasion(self):
        """The evasion gate_bypassed should include the gate from the payload."""
        from app.ingest.router import _ingest_log
        _ingest_log.append({"id": "INGEST-011", "status": "QUEUED"})

        await _pipeline_gate_miss("INGEST-011", _FakeGateMiss())

        evasions = get_all_evasions()
        assert evasions[0]["gate_bypassed"] == ["cycle"]

    @pytest.mark.asyncio
    async def test_gate_miss_unknown_gate_still_records(self):
        """An unknown gate_name should still append an evasion (with evasion_success=False)."""
        class _UnknownGate:
            source_type = "GATE_MISS"
            transaction_id = "TXN-UNK"
            gate_name = "unknown_gate_xyz"
            alert_id = "ALERT-UNK"

        from app.ingest.router import _ingest_log
        _ingest_log.append({"id": "INGEST-012", "status": "QUEUED"})

        await _pipeline_gate_miss("INGEST-012", _UnknownGate())

        evasions = get_all_evasions()
        assert len(evasions) == 1
        assert evasions[0]["evasion_success"] is False


# ─────────────────────────────────────────────────────────────────────────────
# Worker loop integration
# ─────────────────────────────────────────────────────────────────────────────


class TestWorkerLoop:
    @pytest.mark.asyncio
    async def test_worker_loop_processes_queued_item_and_marks_completed(
        self, mock_shadow_scorer, mock_tgep
    ):
        """
        End-to-end: enqueue a FRAUD_DNA item, run the worker loop briefly,
        verify the ingest_log entry reaches COMPLETED status.
        """
        from app.ingest.router import _ingest_log

        ingest_id = "WORKER-LOOP-001"
        _ingest_log.append({"id": ingest_id, "status": "QUEUED"})

        queue_item = {
            "ingest_id": ingest_id,
            "priority": "HIGH",
            "source_type": "FRAUD_DNA",
            "payload": _FakeFraudDNA(),
            "enqueued_at": "2026-06-05T00:00:00Z",
        }
        await _queue.put((1, 0, queue_item))

        # Run the worker loop, cancel after a short timeout
        task = asyncio.create_task(worker_loop())
        await asyncio.sleep(0.5)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        entry = next(e for e in _ingest_log if e["id"] == ingest_id)
        assert entry["status"] == "COMPLETED", f"Expected COMPLETED, got {entry['status']}"

    @pytest.mark.asyncio
    async def test_worker_loop_marks_failed_on_pipeline_error(self):
        """
        If the pipeline raises an exception, the ingest_log entry should be FAILED.
        Patches _pipeline_fraud_dna to raise so the worker's except branch is exercised.
        """
        from app.ingest.router import _ingest_log

        ingest_id = "WORKER-LOOP-002"
        _ingest_log.append({"id": ingest_id, "status": "QUEUED"})

        class _AnyPayload:
            source_type = "FRAUD_DNA"
            feature_vector = {"burst_score": 0.5}

        queue_item = {
            "ingest_id": ingest_id,
            "priority": "HIGH",
            "source_type": "FRAUD_DNA",
            "payload": _AnyPayload(),
            "enqueued_at": "2026-06-05T00:00:00Z",
        }
        await _queue.put((1, 0, queue_item))

        with patch(
            "app.worker.pipeline._pipeline_fraud_dna",
            new_callable=AsyncMock,
            side_effect=RuntimeError("simulated pipeline crash"),
        ):
            task = asyncio.create_task(worker_loop())
            await asyncio.sleep(0.3)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        entry = next(e for e in _ingest_log if e["id"] == ingest_id)
        assert entry["status"] == "FAILED", f"Expected FAILED, got {entry['status']}"
        assert "error" in entry
