"""
Tests — Ingest Router (Task 4.1)
==================================
- test_dedup: same transaction_id twice → second gets 409 Conflict
- test_priority_fraud_dna: FRAUD_DNA → priority=HIGH
- test_priority_novelty_critical: NOVELTY occurrence_count>=15 → CRITICAL
- test_priority_novelty_high: NOVELTY occurrence_count<15 → HIGH
- test_priority_gate_miss: GATE_MISS → MEDIUM
- test_schema_validation_missing_fields: missing required → 422
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.ingest.router import reset_state


@pytest.fixture(autouse=True)
def clean_state():
    """Reset in-memory ingest state before every test."""
    reset_state()
    yield
    reset_state()


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app, raise_server_exceptions=True)


_HEADERS = {"X-API-Key": "changeme"}

_FRAUD_DNA_PAYLOAD = {
    "source_type": "FRAUD_DNA",
    "transaction_id": "TXN-001",
    "account_id": "ACC-001",
    "confirmed_archetype": "structuring",
    "feature_vector": {
        "amount_series_score": 0.9,
        "txn_count_30d": 0.8,
        "amount_vs_threshold_50000": 0.95,
        "burst_score": 0.7,
        "velocity_ratio": 0.6,
    },
    "shap_values": {
        "amount_series_score": 0.3,
        "txn_count_30d": 0.2,
    },
    "timestamp": "2026-06-04T10:00:00Z",
}

_NOVELTY_PAYLOAD_CRITICAL = {
    "source_type": "NOVELTY",
    "fingerprint_id": "FP-001",
    "structural_features": {"bipartite_score": 0.8, "fan_out_ratio": 0.7},
    "occurrence_count": 15,
    "escalated_at": "2026-06-04T10:00:00Z",
}

_NOVELTY_PAYLOAD_HIGH = {
    "source_type": "NOVELTY",
    "fingerprint_id": "FP-002",
    "structural_features": {"bipartite_score": 0.5},
    "occurrence_count": 8,
    "escalated_at": "2026-06-04T10:00:00Z",
}

_GATE_MISS_PAYLOAD = {
    "source_type": "GATE_MISS",
    "transaction_id": "TXN-002",
    "gate_name": "cycle",
    "alert_id": "ALERT-001",
    "missed_at": "2026-06-04T10:00:00Z",
    "investigator_note": "Cycle gate missed this — 9-hop path",
}


class TestDeduplication:
    def test_dedup_same_transaction_id_returns_409(self, client):
        """Sending the same FRAUD_DNA transaction twice must yield 409 on second."""
        r1 = client.post("/red-team/ingest", json=_FRAUD_DNA_PAYLOAD, headers=_HEADERS)
        assert r1.status_code == 202, r1.text

        r2 = client.post("/red-team/ingest", json=_FRAUD_DNA_PAYLOAD, headers=_HEADERS)
        assert r2.status_code == 409, r2.text
        body = r2.json()
        assert body["detail"]["error"] == "duplicate_signal"
        assert "existing_ingest_id" in body["detail"]

    def test_dedup_same_fingerprint_id_returns_409(self, client):
        """Sending the same NOVELTY fingerprint twice must yield 409 on second."""
        r1 = client.post("/red-team/ingest", json=_NOVELTY_PAYLOAD_CRITICAL, headers=_HEADERS)
        assert r1.status_code == 202, r1.text

        r2 = client.post("/red-team/ingest", json=_NOVELTY_PAYLOAD_CRITICAL, headers=_HEADERS)
        assert r2.status_code == 409, r2.text

    def test_different_transactions_both_accepted(self, client):
        """Two different transaction IDs must both be accepted."""
        r1 = client.post("/red-team/ingest", json=_FRAUD_DNA_PAYLOAD, headers=_HEADERS)
        assert r1.status_code == 202

        payload2 = dict(_FRAUD_DNA_PAYLOAD)
        payload2["transaction_id"] = "TXN-999"
        r2 = client.post("/red-team/ingest", json=payload2, headers=_HEADERS)
        assert r2.status_code == 202


class TestPriorityAssignment:
    def test_fraud_dna_priority_high(self, client):
        r = client.post("/red-team/ingest", json=_FRAUD_DNA_PAYLOAD, headers=_HEADERS)
        assert r.status_code == 202
        assert r.json()["priority"] == "HIGH"

    def test_novelty_occurrence_15_priority_critical(self, client):
        r = client.post("/red-team/ingest", json=_NOVELTY_PAYLOAD_CRITICAL, headers=_HEADERS)
        assert r.status_code == 202
        assert r.json()["priority"] == "CRITICAL"

    def test_novelty_occurrence_below_15_priority_high(self, client):
        r = client.post("/red-team/ingest", json=_NOVELTY_PAYLOAD_HIGH, headers=_HEADERS)
        assert r.status_code == 202
        assert r.json()["priority"] == "HIGH"

    def test_gate_miss_priority_medium(self, client):
        r = client.post("/red-team/ingest", json=_GATE_MISS_PAYLOAD, headers=_HEADERS)
        assert r.status_code == 202
        assert r.json()["priority"] == "MEDIUM"


class TestSchemaValidation:
    def test_missing_transaction_id_returns_422(self, client):
        payload = dict(_FRAUD_DNA_PAYLOAD)
        del payload["transaction_id"]
        r = client.post("/red-team/ingest", json=payload, headers=_HEADERS)
        assert r.status_code == 422

    def test_missing_feature_vector_returns_422(self, client):
        payload = dict(_FRAUD_DNA_PAYLOAD)
        del payload["feature_vector"]
        r = client.post("/red-team/ingest", json=payload, headers=_HEADERS)
        assert r.status_code == 422

    def test_invalid_archetype_returns_422(self, client):
        payload = dict(_FRAUD_DNA_PAYLOAD)
        payload["confirmed_archetype"] = "NOT_A_REAL_ARCHETYPE"
        r = client.post("/red-team/ingest", json=payload, headers=_HEADERS)
        assert r.status_code == 422

    def test_invalid_gate_name_returns_422(self, client):
        payload = dict(_GATE_MISS_PAYLOAD)
        payload["gate_name"] = "nonexistent_gate"
        r = client.post("/red-team/ingest", json=payload, headers=_HEADERS)
        assert r.status_code == 422

    def test_missing_api_key_returns_403(self, client):
        r = client.post("/red-team/ingest", json=_FRAUD_DNA_PAYLOAD)
        assert r.status_code == 403

    def test_wrong_api_key_returns_403(self, client):
        r = client.post(
            "/red-team/ingest",
            json=_FRAUD_DNA_PAYLOAD,
            headers={"X-API-Key": "wrongkey"},
        )
        assert r.status_code == 403

    def test_ingest_returns_ingest_id_and_queued_for(self, client):
        r = client.post("/red-team/ingest", json=_FRAUD_DNA_PAYLOAD, headers=_HEADERS)
        assert r.status_code == 202
        body = r.json()
        assert "ingest_id" in body
        assert "priority" in body
        assert "queued_for" in body
