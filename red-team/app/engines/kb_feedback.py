"""
KB Feedback Loop — Adaptive Mutation Weight Engine
===================================================
Reads evasion_kb to compute per-mutation-type success rates and returns
a weight dict. High-success mutations float to the front of the candidate
list in generate_mutations(). Low-success mutations are deprioritised.

Weight formula:
  no history          → weight = 1.0
  success_rate > 0.5  → weight = 1.0 + success_rate  (range: 1.5 – 2.0)
  success_rate < 0.2  → weight = max(0.3, success_rate * 2)  (range: 0.0 – 0.4)
  0.2 ≤ rate ≤ 0.5    → weight = 1.0  (neutral band)
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def get_mutation_weights() -> dict[str, float]:
    """Read evasion_kb and return per-mutation-type adaptive weights.

    Returns:
        dict mapping mutation_type → float weight.
        Unseen mutation types are not included (caller defaults to 1.0).
    """
    try:
        from app.knowledge.kb_store import get_all_evasions
        rows: list[dict[str, Any]] = get_all_evasions()
    except Exception:
        # KB unavailable (e.g. isolated test) — return empty (neutral)
        return {}

    if not rows:
        return {}

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
        rate = successes[mt] / total

        if rate > 0.5:
            weights[mt] = 1.0 + rate          # 1.5 – 2.0  → float to front
        elif rate < 0.2:
            weights[mt] = max(0.3, rate * 2)  # 0.0 – 0.4  → deprioritise
        else:
            weights[mt] = 1.0                 # neutral band

    return weights


def get_top_mutations(n: int = 5) -> list[str]:
    """Return the n mutation_types with the highest success rates.

    Returns an empty list if the KB is empty or unavailable.
    """
    weights = get_mutation_weights()
    if not weights:
        return []

    return sorted(weights, key=lambda mt: weights[mt], reverse=True)[:n]
