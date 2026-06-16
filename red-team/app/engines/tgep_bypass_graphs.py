"""
TGEP Bypass Graphs — Realistic transaction graphs that bypass Blue Team graph gates
====================================================================================
Each graph pattern generates a list of edge dicts designed to:
  1. Bypass Blue Team's graph gates (cycle, sink, bipartite, cash_mule_sink)
  2. Have a chance of also bypassing TGEP detection
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

VALID_BYPASS_TYPES = frozenset({
    "sink_with_outflow", "slow_bipartite", "nine_hop_linear", "mule_warmup_graph",
})

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _edge(from_account: str, to_account: str, amount: float,
          payment_rail: str, timestamp: datetime) -> dict[str, Any]:
    return {
        "from_account": from_account,
        "to_account": to_account,
        "amount": amount,
        "payment_rail": payment_rail,
        "timestamp": timestamp.isoformat(),
    }


def _generate_sink_with_outflow() -> list[dict[str, Any]]:
    """Defeat sink gate by adding legitimate-looking outflows."""
    base = _now().replace(hour=10, minute=0, second=0)
    edges = [
        _edge("corp_A", "target_acct", 300000, "RTGS", base),
        _edge("corp_B", "target_acct", 450000, "RTGS", base + timedelta(days=1, hours=2)),
        _edge("corp_C", "target_acct", 380000, "NEFT", base + timedelta(days=2, hours=1)),
        _edge("target_acct", "payroll_acct", 150000, "NEFT", base + timedelta(hours=4)),
        _edge("target_acct", "utility_co", 35000, "UPI", base + timedelta(days=1, hours=5)),
        _edge("target_acct", "invest_acct", 65000, "IMPS", base + timedelta(days=2, hours=3)),
    ]
    return edges


def _generate_slow_bipartite() -> list[dict[str, Any]]:
    """Defeat bipartite gate: 6 senders (below 7), spread over 5 days."""
    base = _now().replace(hour=10, minute=0, second=0)
    amounts = [82000, 91000, 78000, 88000, 95000, 85000]
    rails = ["UPI", "IMPS", "NEFT", "UPI", "IMPS", "NEFT"]
    edges = []
    for i in range(6):
        ts = base + timedelta(days=i, hours=2 + (i % 3))
        edges.append(_edge(f"sender_S{i+1}", "collector_acct", amounts[i], rails[i], ts))
    return edges


def _generate_nine_hop_linear() -> list[dict[str, Any]]:
    """Defeat cycle gate: 9 linear hops (above 2-8 detection range)."""
    base = _now().replace(hour=11, minute=0, second=0)
    accounts = [chr(65 + i) for i in range(9)]  # A through I
    amount = 500000.0
    rails = ["UPI", "IMPS", "NEFT", "RTGS", "UPI", "IMPS", "NEFT", "RTGS"]
    edges = []
    for i in range(8):
        edges.append(_edge(
            f"acct_{accounts[i]}", f"acct_{accounts[i+1]}",
            round(amount * (0.98 ** i), 2),
            rails[i],
            base + timedelta(minutes=8 * i),
        ))
    return edges


def _generate_mule_warmup_graph() -> list[dict[str, Any]]:
    """Simulate 30-day warmup phase defeating dormancy + cash mule detection."""
    base = _now().replace(hour=10, minute=0, second=0) - timedelta(days=30)
    edges = []

    # Week 1: 3 small receives, 2 small sends
    for i in range(3):
        edges.append(_edge(f"legit_src_{i}", "mule_acct", 2000 + i * 1500, "UPI",
                           base + timedelta(days=i, hours=11 + i)))
    for i in range(2):
        edges.append(_edge("mule_acct", f"shop_{i}", 1500 + i * 500, "UPI",
                           base + timedelta(days=i + 1, hours=14 + i)))

    # Week 2: 4 receives, 3 sends
    for i in range(4):
        edges.append(_edge(f"legit_src_w2_{i}", "mule_acct", 5000 + i * 2500, "IMPS",
                           base + timedelta(days=7 + i, hours=10 + i)))
    for i in range(3):
        edges.append(_edge("mule_acct", f"vendor_{i}", 4000 + i * 1000, "UPI",
                           base + timedelta(days=8 + i, hours=15 + i)))

    # Week 3: 5 receives, 4 sends
    for i in range(5):
        edges.append(_edge(f"legit_src_w3_{i}", "mule_acct", 10000 + i * 5000, "NEFT",
                           base + timedelta(days=14 + i, hours=9 + i)))
    for i in range(4):
        edges.append(_edge("mule_acct", f"payee_{i}", 8000 + i * 2000, "IMPS",
                           base + timedelta(days=15 + i, hours=13 + i)))

    # Week 4: the spike — 1 large receive + 4-hop layering
    spike_time = base + timedelta(days=25, hours=11)
    edges.append(_edge("high_value_src", "mule_acct", 850000, "RTGS", spike_time))
    layer_accounts = ["layer_1", "layer_2", "layer_3", "layer_4"]
    layer_amount = 850000.0
    for i, acct in enumerate(layer_accounts):
        src = "mule_acct" if i == 0 else layer_accounts[i - 1]
        layer_amount *= 0.97
        edges.append(_edge(src, acct, round(layer_amount, 2), "IMPS",
                           spike_time + timedelta(hours=1 + i)))

    return edges


_GENERATORS = {
    "sink_with_outflow": _generate_sink_with_outflow,
    "slow_bipartite": _generate_slow_bipartite,
    "nine_hop_linear": _generate_nine_hop_linear,
    "mule_warmup_graph": _generate_mule_warmup_graph,
}


def generate_tgep_bypass_graph(archetype: str, evasion_type: str) -> dict[str, Any]:
    """Generate a TGEP bypass graph pattern.

    Returns:
        {evasion_type, archetype, edges, edge_count, mutation_type}
    """
    if evasion_type not in VALID_BYPASS_TYPES:
        raise ValueError(f"Unknown evasion_type '{evasion_type}'. Valid: {sorted(VALID_BYPASS_TYPES)}")

    edges = _GENERATORS[evasion_type]()
    return {
        "evasion_type": evasion_type,
        "archetype": archetype,
        "edges": edges,
        "edge_count": len(edges),
        "mutation_type": f"graph_bypass_{evasion_type}",
    }
