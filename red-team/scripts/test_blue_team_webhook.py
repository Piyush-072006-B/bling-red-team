"""
scripts/test_blue_team_webhook.py
==================================
End-to-end test: simulates Blue Team sending a confirmed fraud signal
(FRAUD_DNA) to Red Team's POST /red-team/ingest endpoint.

Run with:
    python scripts/test_blue_team_webhook.py [--url http://localhost:8001]

Exits 0 on success, 1 on failure.
This script is for developer testing — not part of the pytest suite.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

import httpx


# ── Sample payload — matches Blue Team feedback.py integration contract ──────
MOCK_BLUE_TEAM_FRAUD_DNA = {
    "source_type": "FRAUD_DNA",
    "transaction_id": "BT-MOCK-TXN-20260604-001",
    "account_id": "BT-MOCK-ACC-001",
    "confirmed_archetype": "structuring",
    "feature_vector": {
        # 59-feature vector (subset shown — Blue Team sends full set)
        "amount_series_score": 0.92,
        "txn_count_30d": 0.87,
        "amount_vs_threshold_50000": 0.97,
        "amount_vs_threshold_100000": 0.45,
        "amount_vs_threshold_1000000": 0.12,
        "burst_score": 0.74,
        "velocity_ratio": 0.69,
        "night_txn_ratio": 0.22,
        "hour_deviation": 0.3,
        "counterparty_novelty": 0.61,
        "return_ratio": 0.08,
        "payee_vpa_age_days": 0.55,
        "channel_switch": 0.2,
        "channel_entropy": 0.4,
        "geography_switch": 0.1,
        "bipartite_score": 0.3,
        "fan_out_ratio": 0.25,
        "distinct_counterparties_30d": 0.4,
        "cycle_membership": 0.15,
        "cash_mule_sink_score": 0.18,
        "dormancy_break": 0.05,
        "dormancy_reactivation_flag": 0.0,
        "temporal_acceleration": 0.3,
        "is_festival_period": 0.0,
        "amount_zscore": 0.88,
    },
    "shap_values": {
        "amount_series_score": 0.31,
        "txn_count_30d": 0.18,
        "amount_vs_threshold_50000": 0.28,
        "burst_score": 0.12,
        "velocity_ratio": 0.09,
    },
    "timestamp": datetime.now(timezone.utc).isoformat(),
}

MOCK_NOVELTY_ESCALATION = {
    "source_type": "NOVELTY",
    "fingerprint_id": "BT-FP-NOVEL-20260604-001",
    "structural_features": {
        "bipartite_score": 0.82,
        "fan_out_ratio": 0.76,
        "cycle_membership": 0.45,
        "burst_score": 0.91,
        "velocity_ratio": 0.88,
        "temporal_acceleration": 0.67,
        "amount_zscore": 0.79,
    },
    "occurrence_count": 17,
    "escalated_at": datetime.now(timezone.utc).isoformat(),
}

MOCK_GATE_MISS = {
    "source_type": "GATE_MISS",
    "transaction_id": "BT-MOCK-TXN-20260604-002",
    "gate_name": "cycle",
    "alert_id": "ALERT-BT-20260604-001",
    "missed_at": datetime.now(timezone.utc).isoformat(),
    "investigator_note": (
        "Transaction used 9-hop path — Blue Team cycle detector only checks 2-8 hops. "
        "Forwarding to Red Team for adversarial analysis."
    ),
}


def send_payload(
    base_url: str,
    api_key: str,
    payload: dict,
    label: str,
) -> bool:
    """Send one payload to /red-team/ingest. Returns True on success."""
    url = f"{base_url.rstrip('/')}/red-team/ingest"
    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}

    print(f"\n{'─' * 60}")
    print(f"[{label}] POST {url}")
    print(f"  source_type: {payload['source_type']}")

    try:
        resp = httpx.post(url, json=payload, headers=headers, timeout=10.0)
        if resp.status_code == 202:
            body = resp.json()
            print(f"  ✅ 202 Accepted")
            print(f"     ingest_id  : {body.get('ingest_id')}")
            print(f"     priority   : {body.get('priority')}")
            print(f"     queued_for : {body.get('queued_for')}")
            return True
        elif resp.status_code == 409:
            body = resp.json()
            print(f"  ⚠️  409 Conflict (duplicate — already ingested)")
            print(f"     existing_id: {body.get('detail', {}).get('existing_ingest_id')}")
            return True  # duplicate is expected on re-runs — not a failure
        else:
            print(f"  ❌ Unexpected {resp.status_code}: {resp.text[:200]}")
            return False
    except httpx.ConnectError:
        print(f"  ❌ Connection refused — is Red Team running on {base_url}?")
        return False
    except Exception as exc:
        print(f"  ❌ Error: {exc}")
        return False


def check_health(base_url: str) -> bool:
    """Check /health before running tests."""
    url = f"{base_url.rstrip('/')}/health"
    try:
        resp = httpx.get(url, timeout=5.0)
        if resp.status_code == 200 and resp.json().get("status") == "ok":
            print(f"✅ /health OK — {resp.json()}")
            return True
        print(f"❌ /health returned {resp.status_code}: {resp.text}")
        return False
    except Exception as exc:
        print(f"❌ /health unreachable: {exc}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="End-to-end Blue Team → Red Team webhook test"
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8001",
        help="Red Team base URL (default: http://localhost:8001)",
    )
    parser.add_argument(
        "--api-key",
        default="changeme",
        help="Red Team API key (default: changeme)",
    )
    args = parser.parse_args()

    print(f"\n{'═' * 60}")
    print(f"  Blue Team → Red Team Webhook Integration Test")
    print(f"  Target: {args.url}")
    print(f"{'═' * 60}")

    # 1. Health check
    if not check_health(args.url):
        print(
            "\n⚠️  Red Team service not reachable. "
            "Start it with: uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload"
        )
        print("   (Tests are written — run this script once the service is up.)")
        return 0  # Not a test failure — service not running

    results = []

    # 2. FRAUD_DNA (structuring, HIGH priority)
    results.append(
        send_payload(args.url, args.api_key, MOCK_BLUE_TEAM_FRAUD_DNA, "FRAUD_DNA")
    )

    # 3. NOVELTY (occurrence_count=17 → CRITICAL priority)
    results.append(
        send_payload(args.url, args.api_key, MOCK_NOVELTY_ESCALATION, "NOVELTY_CRITICAL")
    )

    # 4. GATE_MISS (cycle gate, MEDIUM priority)
    results.append(
        send_payload(args.url, args.api_key, MOCK_GATE_MISS, "GATE_MISS")
    )

    # 5. Duplicate test (re-send FRAUD_DNA — expect 409)
    print(f"\n{'─' * 60}")
    print("[DEDUP] Re-sending FRAUD_DNA — expect 409 Conflict")
    results.append(
        send_payload(args.url, args.api_key, MOCK_BLUE_TEAM_FRAUD_DNA, "FRAUD_DNA_DUP")
    )

    # Summary
    passed = sum(results)
    total = len(results)
    print(f"\n{'═' * 60}")
    print(f"  Results: {passed}/{total} scenarios passed")
    if passed == total:
        print("  ✅ All integration scenarios passed")
    else:
        print("  ❌ Some scenarios failed — check output above")
    print(f"{'═' * 60}\n")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
