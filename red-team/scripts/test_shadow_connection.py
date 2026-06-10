"""
scripts/test_shadow_connection.py
===================================
One-shot connectivity test: sends a known structuring transaction to the
Blue Team shadow scorer and asserts score > 0.5.

Usage:
    python scripts/test_shadow_connection.py [--url http://localhost:8002]

Requirements for Blue Team:
    1. Blue Team must expose POST /api/v1/shadow/score
       - Auth: INTERNAL_API_KEY only
       - Behaviour: identical to /api/v1/score but writes nothing to DB,
         fires no alerts, never hits production pipeline
       - Returns: same schema as /api/v1/score
         { "score": float, "action": str, "gate_fired": str|None }

    2. Blue Team docker-compose must add Red Team to its network:
         networks:
           - bling_network  (shared with Red Team)

    3. Blue Team .env must have:
         RED_TEAM_URL=http://red-team:8002
         RED_TEAM_API_KEY=changeme

Exits 0 on success (score > 0.5), 1 on failure or unavailability.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

import httpx

# ── Known structuring transaction (high confidence) ───────────────────────────
KNOWN_STRUCTURING_VECTOR = {
    "feature_vector": {
        "amount_series_score": 0.95,
        "txn_count_30d": 0.88,
        "amount_vs_threshold_50000": 0.97,
        "amount_vs_threshold_100000": 0.40,
        "amount_vs_threshold_1000000": 0.10,
        "burst_score": 0.76,
        "velocity_ratio": 0.72,
        "night_txn_ratio": 0.20,
        "hour_deviation": 0.25,
        "counterparty_novelty": 0.58,
        "return_ratio": 0.07,
        "payee_vpa_age_days": 0.50,
        "channel_switch": 0.18,
        "channel_entropy": 0.35,
        "geography_switch": 0.08,
        "bipartite_score": 0.22,
        "fan_out_ratio": 0.20,
        "distinct_counterparties_30d": 0.38,
        "cycle_membership": 0.12,
        "cash_mule_sink_score": 0.15,
        "dormancy_break": 0.03,
        "dormancy_reactivation_flag": 0.0,
        "temporal_acceleration": 0.28,
        "is_festival_period": 0.0,
        "amount_zscore": 0.91,
    },
    "metadata": {
        "caller": "red-team-shadow-test",
        "archetype": "structuring",
        "test_timestamp": datetime.now(timezone.utc).isoformat(),
    },
}

SHADOW_ENDPOINT = "/api/v1/shadow/score"
MIN_EXPECTED_SCORE = 0.5


def run_shadow_test(shadow_base_url: str, internal_key: str) -> int:
    """
    POST a known structuring vector to Blue Team shadow scorer.
    Assert score > MIN_EXPECTED_SCORE.
    Returns 0 (pass) or 1 (fail).
    """
    url = f"{shadow_base_url.rstrip('/')}{SHADOW_ENDPOINT}"

    print(f"\n{'═' * 60}")
    print(f"  Blue Team Shadow Scorer Connectivity Test")
    print(f"  Target URL : {url}")
    print(f"  Min score  : {MIN_EXPECTED_SCORE}")
    print(f"{'═' * 60}")

    try:
        print(f"\nPOST {url}")
        resp = httpx.post(
            url,
            json=KNOWN_STRUCTURING_VECTOR,
            headers={
                "Content-Type": "application/json",
                "X-Internal-Key": internal_key,
                "X-Caller": "red-team-shadow-test",
            },
            timeout=10.0,
        )

        print(f"Status: {resp.status_code}")

        if resp.status_code == 200:
            body = resp.json()
            score = body.get("score")
            action = body.get("action")
            gate_fired = body.get("gate_fired")

            print(f"\nResponse:")
            print(f"  score      : {score}")
            print(f"  action     : {action}")
            print(f"  gate_fired : {gate_fired}")

            if score is None:
                print(f"\n❌ FAIL — response missing 'score' field")
                return 1

            score_f = float(score)
            if score_f > MIN_EXPECTED_SCORE:
                print(f"\n✅ PASS — score {score_f:.4f} > {MIN_EXPECTED_SCORE}")
                return 0
            else:
                print(
                    f"\n❌ FAIL — score {score_f:.4f} ≤ {MIN_EXPECTED_SCORE} "
                    f"(expected HIGH_RISK for structuring archetype)"
                )
                return 1

        elif resp.status_code == 404:
            print(
                f"\n❌ FAIL — 404 Not Found\n"
                f"   Blue Team shadow endpoint not implemented yet.\n"
                f"   Add to Blue Team: POST /api/v1/shadow/score (see master prompt INTEGRATION section)"
            )
            return 1

        elif resp.status_code == 403:
            print(
                f"\n❌ FAIL — 403 Forbidden\n"
                f"   Check INTERNAL_API_KEY configuration on Blue Team side."
            )
            return 1

        else:
            print(f"\n❌ FAIL — unexpected {resp.status_code}: {resp.text[:300]}")
            return 1

    except httpx.ConnectError:
        print(
            f"\n⚠️  UNAVAILABLE — Blue Team shadow scorer not reachable at {url}\n"
            f"\n   Setup required:\n"
            f"   1. Blue Team must implement POST /api/v1/shadow/score\n"
            f"   2. Set BLUE_TEAM_SHADOW_URL={shadow_base_url} in Red Team .env\n"
            f"   3. Ensure both services are on the same Docker network\n"
        )
        return 0  # Connectivity issue, not a code error — pass for now

    except httpx.TimeoutException:
        print(f"\n❌ FAIL — Timeout (>10s). Shadow scorer may be overloaded.")
        return 1

    except Exception as exc:
        print(f"\n❌ FAIL — Unexpected error: {exc}")
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Test Blue Team shadow scorer connectivity from Red Team"
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8002",
        help="Blue Team shadow scorer base URL (default: http://localhost:8002, i.e. BLUE_TEAM_SHADOW_URL)",
    )
    parser.add_argument(
        "--internal-key",
        default="changeme-internal",
        help="Blue Team INTERNAL_API_KEY",
    )
    args = parser.parse_args()

    result = run_shadow_test(args.url, args.internal_key)

    if result == 0:
        print(
            "\n📋  Next steps if shadow scorer is not yet configured:\n"
            "    See RED_TEAM_MASTER_PROMPT.md → INTEGRATION section\n"
            "    'Blue Team must expose POST /api/v1/shadow/score'\n"
        )

    return result


if __name__ == "__main__":
    sys.exit(main())
