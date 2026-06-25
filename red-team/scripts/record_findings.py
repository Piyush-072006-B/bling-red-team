"""
Record Findings — Formally record 3 confirmed Red Team findings in evasion KB.
===============================================================================
Run once after server starts. Findings appear in GET /red-team/briefing
as immediate_action_required items (severity CRITICAL or HIGH).

Usage:
    python scripts/record_findings.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))


def record_all_findings() -> None:
    from app.knowledge.kb_store import append_evasion

    findings = [
        # ── Finding 1: CRITICAL — 9-hop cycle gate blind spot ──────────────
        {
            "archetype": "cycle_round_trip",
            "mutation_type": "graph_bypass_nine_hop_linear",
            "severity": "CRITICAL",
            "gate_bypassed": ["cycle"],
            "evasion_success": True,
            "context_multiplier_abused": None,
            "tgep_threat_level": "CRITICAL",
            "tgep_patterns_detected": ["circular_laundering"],
            "tgep_recommended_patch": "Extend Blue Team cycle gate from 8 hops to 10",
            "evasion_vector": {},
            "feature_deltas": {"cycle_membership": -1.0, "return_ratio": -0.58},
            "score_original": 0.92,
            "score_mutated": 0.31,
            "ingest_log_id": "confirmed_finding_001",
        },
        # ── Finding 2: HIGH — senior+night timing bypass ────────────────────
        {
            "archetype": "digital_arrest",
            "mutation_type": "timing_day",
            "severity": "HIGH",
            "gate_bypassed": ["context_senior_night"],
            "evasion_success": True,
            "context_multiplier_abused": "senior_night_1.50x",
            "tgep_threat_level": "HIGH",
            "tgep_patterns_detected": ["layering_chain"],
            "tgep_recommended_patch": (
                "Add 7-day rolling night_txn_ratio baseline in Blue Team"
            ),
            "evasion_vector": {"night_txn_ratio": 0.05, "hour_of_day": 14.0},
            "feature_deltas": {"night_txn_ratio": -0.40, "hour_of_day": 11.0},
            "score_original": 0.88,
            "score_mutated": 0.42,
            "ingest_log_id": "confirmed_finding_002",
        },
        # ── Finding 3: CRITICAL — sink/accumulation evades BOTH systems ─────
        {
            "archetype": "ghost_node_cash",
            "mutation_type": "graph_bypass_sink_with_outflow",
            "severity": "CRITICAL",
            "gate_bypassed": ["sink"],
            "evasion_success": True,
            "context_multiplier_abused": None,
            "tgep_threat_level": None,
            "tgep_patterns_detected": [],
            "tgep_recommended_patch": (
                "Add inflow/outflow ratio analysis to both Blue Team sink gate and TGEP "
                "graph analyzer — this pattern evades BOTH systems"
            ),
            "evasion_vector": {},
            "feature_deltas": {"sink_score": -0.65, "fan_out_ratio": 2.2},
            "score_original": 0.91,
            "score_mutated": 0.28,
            "ingest_log_id": "confirmed_finding_003",
        },
    ]

    for i, finding in enumerate(findings, 1):
        row_id = append_evasion(finding)
        print(
            f"[record_findings] {i}/{len(findings)} recorded  "
            f"archetype={finding['archetype']:20s}  "
            f"severity={finding['severity']:8s}  "
            f"row_id={row_id[:8]}..."
        )

    print(f"\n[record_findings] Done — {len(findings)} confirmed findings in evasion KB.")
    print("[record_findings] They will appear under immediate_action_required in GET /red-team/briefing")


if __name__ == "__main__":
    record_all_findings()
