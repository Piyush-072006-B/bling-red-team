"""
KB Feedback Loop — Adaptive Mutation Weight Engine
===================================================
Reads evasion_kb to compute per-mutation-type success rates and
returns a weight dict. High-success mutations are weighted higher
so they float to the front of the candidates list in mutation_engine.py.

Weight formula:
  success_rate > 0.5  → weight = 1.0 + success_rate   (range: 1.5 – 2.0)
  success_rate < 0.2  → weight = max(0.3, success_rate * 2)  (range: 0.3 – 0.4)
  0.2 ≤ rate ≤ 0.5    → weight = 1.0
  no history          → weight = 1.0
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def get_mutation_weights() -> dict[str, float]:
    """Read evasion_kb and return per-mutation-type weights.

    Returns:
        dict mapping mutation_type → float weight.
        Unknown/unseen types default to 1.0.
    """
    try:
        from app.knowledge.kb_store import get_all_evasions
        rows: list[dict[str, Any]] = get_all_evasions()
    except Exception:
        # KB not available (e.g. test isolation) — neutral weights
        return {}

    if not rows:
        return {}

    # Aggregate per mutation_type: count total, count successes
    totals: dict[str, int] = defaultdict(int)
    successes: dict[str, int] = defaultdict(int)

    for row in rows:
        mt = row.get("mutation_type")
        if not mt:
            continue
        totals[mt] += 1
        if row.get("evasion_success"):
            successes[mt] += 1

    weights: dict[str, float] = {}
    for mt, total in totals.items():
        success_rate = successes[mt] / total

        if success_rate > 0.5:
            weights[mt] = 1.0 + success_rate       # 1.5 – 2.0
        elif success_rate < 0.2:
            weights[mt] = max(0.3, success_rate * 2)  # 0.3 – 0.4
        else:
            weights[mt] = 1.0                       # neutral band

    return weights
