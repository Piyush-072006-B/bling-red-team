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
    c = "ACC990477"
    edges = [
        _edge("CORP991", c, 300000, "RTGS", base),
        _edge("CORP992", c, 450000, "RTGS", base + timedelta(days=1, hours=2)),
        _edge("CORP993", c, 380000, "NEFT", base + timedelta(days=2, hours=1)),
        _edge(c, "PAYROLL_VENDOR_994", 150000, "NEFT", base + timedelta(hours=4)),
        _edge(c, "UTIL_PROVIDER_995", 35000, "UPI", base + timedelta(days=1, hours=5)),
        _edge(c, "INVEST_FUND_996", 65000, "IMPS", base + timedelta(days=2, hours=3)),
    ]
    return edges


def _generate_slow_bipartite() -> list[dict[str, Any]]:
    """Defeat bipartite gate using stealth sink structure (6 inflows, legitimate outflows)."""
    base = _now().replace(hour=10, minute=0, second=0)
    c = "ACC100588"
    amounts = [82000, 91000, 78000, 88000, 95000, 85000]
    rails = ["UPI", "IMPS", "NEFT", "UPI", "IMPS", "NEFT"]
    edges = []
    # 6 Inflows
    for i in range(6):
        ts = base + timedelta(days=i, hours=2 + (i % 3))
        edges.append(_edge(f"CORP{101+i}", c, amounts[i], rails[i], ts))
    
    # Legitimate outflows
    outflows = [
        ("PAYROLL_VENDOR_107", 110000, "NEFT", 1, 4),
        ("VENDOR_108", 25000, "UPI", 3, 5),
        ("INVEST_FUND_109", 40000, "IMPS", 5, 2)
    ]
    for dst, amt, rail, d, h in outflows:
        edges.append(_edge(c, dst, amt, rail, base + timedelta(days=d, hours=h)))
        
    return edges


def _generate_nine_hop_linear() -> list[dict[str, Any]]:
    """Defeat cycle gate using multi-source sink instead of linear chain."""
    base = _now().replace(hour=11, minute=0, second=0)
    c = "ACC210699"
    edges = [
        _edge("CORP211", c, 200000, "NEFT", base),
        _edge("CORP212", c, 180000, "RTGS", base + timedelta(days=1)),
        _edge("CORP213", c, 250000, "IMPS", base + timedelta(days=2)),
        _edge(c, "PAYROLL_VENDOR_214", 120000, "NEFT", base + timedelta(days=3)),
        _edge(c, "VENDOR_215", 35000, "UPI", base + timedelta(days=3, hours=5)),
        _edge(c, "UTIL_PROVIDER_216", 18000, "IMPS", base + timedelta(days=4)),
    ]
    return edges


def _generate_mule_warmup_graph() -> list[dict[str, Any]]:
    """Simulate 30-day warmup phase, but final spike converts to legitimate spend instead of layering."""
    base = _now().replace(hour=10, minute=0, second=0) - timedelta(days=30)
    c = "ACC320711"
    edges = []
    
    # We need a continuous CORP id sequence. Let's start at 321.
    corp_idx = 321
    out_idx = 340

    # Week 1: 3 small receives, 2 small sends
    for i in range(3):
        edges.append(_edge(f"CORP{corp_idx}", c, 2000 + i * 1500, "UPI",
                           base + timedelta(days=i, hours=11 + i)))
        corp_idx += 1
    for i in range(2):
        edges.append(_edge(c, f"VENDOR_{out_idx}", 1500 + i * 500, "UPI",
                           base + timedelta(days=i + 1, hours=14 + i)))
        out_idx += 1

    # Week 2: 4 receives, 3 sends
    for i in range(4):
        edges.append(_edge(f"CORP{corp_idx}", c, 5000 + i * 2500, "IMPS",
                           base + timedelta(days=7 + i, hours=10 + i)))
        corp_idx += 1
    for i in range(3):
        edges.append(_edge(c, f"VENDOR_{out_idx}", 4000 + i * 1000, "UPI",
                           base + timedelta(days=8 + i, hours=15 + i)))
        out_idx += 1

    # Week 3: 5 receives, 4 sends
    for i in range(5):
        edges.append(_edge(f"CORP{corp_idx}", c, 10000 + i * 5000, "NEFT",
                           base + timedelta(days=14 + i, hours=9 + i)))
        corp_idx += 1
    for i in range(4):
        edges.append(_edge(c, f"PAYROLL_VENDOR_{out_idx}", 8000 + i * 2000, "IMPS",
                           base + timedelta(days=15 + i, hours=13 + i)))
        out_idx += 1

    # Week 4: the spike converts to legitimate spend
    spike_time = base + timedelta(days=25, hours=11)
    edges.append(_edge(f"CORP{corp_idx}", c, 850000, "RTGS", spike_time))
    edges.append(_edge(c, f"PAYROLL_VENDOR_{out_idx}", 150000, "NEFT", spike_time + timedelta(hours=4)))
    edges.append(_edge(c, f"UTIL_PROVIDER_{out_idx+1}", 35000, "UPI", spike_time + timedelta(hours=5)))
    edges.append(_edge(c, f"VENDOR_{out_idx+2}", 65000, "IMPS", spike_time + timedelta(hours=8)))
    edges.append(_edge(c, f"INVEST_FUND_{out_idx+3}", 45000, "RTGS", spike_time + timedelta(hours=10)))

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
