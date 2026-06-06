"""
Tests — Security and Queue fixes
==================================
Covers ISSUE 2 (PII sanitization) and ISSUE 5 (bounded queues / HTTP 503).
"""

from __future__ import annotations

import asyncio
import pytest
from fastapi.testclient import TestClient

from app.ingest.router import (
    _ingest_log,
    _queues,
    reset_state,
)
from app.knowledge.kb_store import reset_kb


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

# Minimal valid FRAUD_DNA payload (shap_values must be non-empty per validator)
_FRAUD_DNA_PAYLOAD = {
    "source_type": "FRAUD_DNA",
    "transaction_id": "TXN-PII-001",
    "account_id": "ACC-PII-001",
    "confirmed_archetype": "structuring",
    "feature_vector": {"burst_score": 0.7},
    "shap_values": {"burst_score": 0.3},
    "timestamp": "2026-06-06T00:00:00Z",
}

# Minimal valid NOVELTY payload
_NOVELTY_PAYLOAD = {
    "source_type": "NOVELTY",
    "fingerprint_id": "FP-PII-001",
    "structural_features": {"bipartite_score": 0.8},
    "occurrence_count": 5,
    "escalated_at": "2026-06-06T00:00:00Z",
}

# Minimal valid GATE_MISS payload
_GATE_MISS_PAYLOAD = {
    "source_type": "GATE_MISS",
    "transaction_id": "TXN-GATE-001",
    "gate_name": "cycle",
    "alert_id": "ALERT-PII-001",
    "missed_at": "2026-06-06T00:00:00Z",
    "investigator_note": "test",
}


# ─────────────────────────────────────────────────────────────────────────────
# ISSUE 2 — PII sanitization
# ─────────────────────────────────────────────────────────────────────────────


class TestPIISanitization:
    def test_raw_account_id_not_in_ingest_log(self, client):
        """Raw account_id must never appear in the ingest log."""
        r = client.post("/red-team/ingest", json=_FRAUD_DNA_PAYLOAD, headers=_HEADERS)
        assert r.status_code == 202, f"Unexpected: {r.status_code} {r.text}"
        for entry in _ingest_log:
            payload_stored = entry.get("raw_payload", {})
            assert payload_stored.get("account_id") != "ACC-PII-001", (
                "Raw account_id found in ingest_log — PII leak!"
            )

    def test_raw_transaction_id_not_in_ingest_log_fraud_dna(self, client):
        """Raw transaction_id must never appear in the ingest log for FRAUD_DNA."""
        r = client.post("/red-team/ingest", json=_FRAUD_DNA_PAYLOAD, headers=_HEADERS)
        assert r.status_code == 202, f"Unexpected: {r.status_code} {r.text}"
        for entry in _ingest_log:
            payload_stored = entry.get("raw_payload", {})
            assert payload_stored.get("transaction_id") != "TXN-PII-001", (
                "Raw transaction_id found in ingest_log — PII leak!"
            )

    def test_raw_fingerprint_id_not_in_ingest_log(self, client):
        """Raw fingerprint_id must never appear in the ingest log for NOVELTY."""
        r = client.post("/red-team/ingest", json=_NOVELTY_PAYLOAD, headers=_HEADERS)
        assert r.status_code == 202, f"Unexpected: {r.status_code} {r.text}"
        for entry in _ingest_log:
            payload_stored = entry.get("raw_payload", {})
            assert payload_stored.get("fingerprint_id") != "FP-PII-001", (
                "Raw fingerprint_id found in ingest_log — PII leak!"
            )

    def test_raw_alert_id_not_in_ingest_log(self, client):
        """Raw alert_id must never appear in the ingest log for GATE_MISS."""
        r = client.post("/red-team/ingest", json=_GATE_MISS_PAYLOAD, headers=_HEADERS)
        assert r.status_code == 202, f"Unexpected: {r.status_code} {r.text}"
        for entry in _ingest_log:
            payload_stored = entry.get("raw_payload", {})
            assert payload_stored.get("alert_id") != "ALERT-PII-001", (
                "Raw alert_id found in ingest_log — PII leak!"
            )

    def test_sanitized_account_id_is_12_char_hash(self, client):
        """Stored account_id should be a 12-character hex hash."""
        r = client.post("/red-team/ingest", json=_FRAUD_DNA_PAYLOAD, headers=_HEADERS)
        assert r.status_code == 202, f"Unexpected: {r.status_code} {r.text}"
        entry = next(
            (e for e in _ingest_log if e["source_type"] == "FRAUD_DNA"), None
        )
        assert entry is not None, "FRAUD_DNA entry not found in ingest_log"
        stored = entry["raw_payload"].get("account_id")
        assert stored is not None
        assert len(stored) == 12
        assert all(c in "0123456789abcdef" for c in stored)

    def test_sanitized_transaction_id_is_12_char_hash(self, client):
        """Stored transaction_id should be a 12-character hex hash."""
        r = client.post("/red-team/ingest", json=_FRAUD_DNA_PAYLOAD, headers=_HEADERS)
        assert r.status_code == 202, f"Unexpected: {r.status_code} {r.text}"
        entry = next(
            (e for e in _ingest_log if e["source_type"] == "FRAUD_DNA"), None
        )
        assert entry is not None
        stored = entry["raw_payload"].get("transaction_id")
        assert stored is not None
        assert len(stored) == 12

    def test_dedup_still_works_after_pii_sanitization(self, client):
        """Deduplication must still function even though raw IDs are sanitized in log."""
        r1 = client.post("/red-team/ingest", json=_FRAUD_DNA_PAYLOAD, headers=_HEADERS)
        assert r1.status_code == 202, f"Unexpected: {r1.status_code} {r1.text}"
        r2 = client.post("/red-team/ingest", json=_FRAUD_DNA_PAYLOAD, headers=_HEADERS)
        assert r2.status_code == 409, "Duplicate should still be caught"


# ─────────────────────────────────────────────────────────────────────────────
# ISSUE 5 — Bounded queues / HTTP 503
# ─────────────────────────────────────────────────────────────────────────────


class TestBoundedQueues:
    def test_503_when_queue_full(self, client):
        """When the HIGH queue is full, POST /red-team/ingest should return 503."""
        # Replace HIGH queue with a maxsize=1 queue so we can fill it cheaply
        original_q = _queues["HIGH"]
        _queues["HIGH"] = asyncio.Queue(maxsize=1)

        try:
            # First item fills the queue (no worker to drain it in this test context)
            r1 = client.post("/red-team/ingest", json=_FRAUD_DNA_PAYLOAD, headers=_HEADERS)
            assert r1.status_code == 202, f"First item should be accepted, got {r1.status_code}: {r1.text}"

            # Second item with a different transaction_id — queue is now full
            payload2 = dict(_FRAUD_DNA_PAYLOAD)
            payload2["transaction_id"] = "TXN-FULL-002"
            r2 = client.post("/red-team/ingest", json=payload2, headers=_HEADERS)
            assert r2.status_code == 503, (
                f"Expected 503 when queue full, got {r2.status_code}: {r2.text}"
            )
            assert r2.json()["detail"]["error"] == "queue_full"
        finally:
            _queues["HIGH"] = original_q

    def test_503_rolls_back_ingest_log_entry(self, client):
        """On queue-full, the ingest_log entry must be rolled back (no phantom entries)."""
        original_q = _queues["HIGH"]
        _queues["HIGH"] = asyncio.Queue(maxsize=1)

        try:
            # Fill queue with first item
            client.post("/red-team/ingest", json=_FRAUD_DNA_PAYLOAD, headers=_HEADERS)

            initial_count = len(_ingest_log)
            payload2 = dict(_FRAUD_DNA_PAYLOAD)
            payload2["transaction_id"] = "TXN-ROLLBACK-001"
            r = client.post("/red-team/ingest", json=payload2, headers=_HEADERS)

            assert r.status_code == 503
            # ingest_log must not have grown — rollback must have occurred
            assert len(_ingest_log) == initial_count, (
                "ingest_log entry was not rolled back on queue-full"
            )
        finally:
            _queues["HIGH"] = original_q

    def test_503_rolls_back_dedup_hash(self, client):
        """On queue-full, the dedup hash must be rolled back so retry succeeds."""
        original_q = _queues["HIGH"]
        _queues["HIGH"] = asyncio.Queue(maxsize=1)

        try:
            # Fill queue
            client.post("/red-team/ingest", json=_FRAUD_DNA_PAYLOAD, headers=_HEADERS)

            payload2 = dict(_FRAUD_DNA_PAYLOAD)
            payload2["transaction_id"] = "TXN-DEDUP-ROLLBACK"
            r = client.post("/red-team/ingest", json=payload2, headers=_HEADERS)
            assert r.status_code == 503

            # Drain the queue to make room, then retry — should now succeed (not 409)
            _queues["HIGH"].get_nowait()

            r2 = client.post("/red-team/ingest", json=payload2, headers=_HEADERS)
            assert r2.status_code == 202, (
                f"Retry after rollback should succeed (not 409 duplicate), got {r2.status_code}"
            )
        finally:
            _queues["HIGH"] = original_q
