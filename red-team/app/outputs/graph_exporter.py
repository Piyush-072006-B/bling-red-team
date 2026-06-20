"""
Graph Exporter — Convert Evasion Findings into TGEP Transaction Graph Format
=============================================================================
Converts any evasion finding (feature-level or graph-level) into a list of
realistic transaction edge dicts ready for TGEP's /transaction/manual endpoint.

Edge schema (per TGEP contract):
    {from_account, to_account, amount, payment_rail, timestamp}

Account name format: RT_{ARCHETYPE_UPPER}_{ROLE}
Timestamp format: "2026-06-17T10:00:00" (no timezone suffix, UTC)
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from app.engines.tgep_bypass_graphs import VALID_BYPASS_TYPES, generate_tgep_bypass_graph


def _utcnow() -> datetime:
    return datetime.utcnow()


def _fmt(dt: datetime) -> str:
    """Format timestamp without timezone suffix as required by TGEP."""
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def _edge(src: str, dst: str, amount: float, rail: str, dt: datetime) -> dict[str, Any]:
    return {
        "from_account": src,
        "to_account": dst,
        "amount": round(amount, 2),
        "payment_rail": rail,
        "timestamp": _fmt(dt),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Archetype-specific graph templates
# ─────────────────────────────────────────────────────────────────────────────


def _graph_digital_arrest(amt: float) -> list[dict]:
    """
    4-hop layering chain from victim to collector + 2 sub-₹50K decoy transfers.
    Total: 7 accounts, all within 2 hours, daytime (10am–12pm).
    """
    base = _utcnow().replace(hour=10, minute=0, second=0, microsecond=0)
    a = "RT_DIGITAL_ARREST"
    return [
        _edge(f"{a}_VICTIM",  f"{a}_MULE_1",     850000, "UPI",  base - timedelta(minutes=2)),
        _edge(f"{a}_VICTIM",  f"{a}_DECOY_1",      49500, "UPI",  base - timedelta(minutes=2)),
        _edge(f"{a}_VICTIM",  f"{a}_DECOY_2",      48800, "UPI",  base - timedelta(minutes=1)),
        _edge(f"{a}_MULE_1",  f"{a}_MULE_2",      825000, "IMPS", base + timedelta(minutes=12)),
        _edge(f"{a}_MULE_2",  f"{a}_MULE_3",      800000, "NEFT", base + timedelta(minutes=28)),
        _edge(f"{a}_MULE_3",  f"{a}_COLLECTOR",   776000, "UPI",  base + timedelta(minutes=47)),
    ]


def _graph_structuring(amt: float) -> list[dict]:
    """
    1 origin → 6 receivers all below ₹50K, mixed rails, within 30 minutes.
    """
    base = _utcnow().replace(hour=10, minute=0, second=0, microsecond=0)
    a = "RT_STRUCTURING"
    specs = [
        (49500, "UPI",  0),
        (49200, "UPI",  5),
        (48800, "IMPS", 10),
        (49000, "UPI",  15),
        (48500, "NEFT", 20),
        (49300, "IMPS", 25),
    ]
    return [
        _edge(f"{a}_ORIGIN", f"{a}_R{i+1}", amount, rail, base + timedelta(minutes=gap))
        for i, (amount, rail, gap) in enumerate(specs)
    ]


def _graph_rapid_layering(amt: float) -> list[dict]:
    """
    6-hop chain, 8-minute gaps, 2% decline per hop.
    Rails cycle UPI → IMPS → NEFT → RTGS → UPI → IMPS.
    """
    base = _utcnow().replace(hour=10, minute=0, second=0, microsecond=0)
    a = "RT_RAPID_LAYERING"
    nodes = ["A", "B", "C", "D", "E", "F", "G"]
    rails = ["UPI", "IMPS", "NEFT", "RTGS", "UPI", "IMPS"]
    amounts = [150000, 147000, 144060, 141178, 138355, 135588]
    return [
        _edge(f"{a}_{nodes[i]}", f"{a}_{nodes[i+1]}", amounts[i], rails[i],
              base + timedelta(minutes=8 * i))
        for i in range(6)
    ]


def _graph_bipartite_mule(amt: float) -> list[dict]:
    """
    6 senders all paying 1 collector within 2 hours.
    """
    base = _utcnow().replace(hour=10, minute=0, second=0, microsecond=0)
    a = "RT_BIPARTITE_MULE"
    specs = [
        (92000, "UPI",  0),
        (88000, "UPI",  20),
        (85000, "IMPS", 40),
        (91000, "UPI",  60),
        (87000, "NEFT", 80),
        (89000, "UPI",  100),
    ]
    return [
        _edge(f"{a}_S{i+1}", f"{a}_COLLECTOR", amount, rail,
              base + timedelta(minutes=gap))
        for i, (amount, rail, gap) in enumerate(specs)
    ]


def _graph_cycle_round_trip(amt: float) -> list[dict]:
    """
    8-hop circular A→B→…→H→A, 2% decline per hop, 10-minute gaps.
    """
    base = _utcnow().replace(hour=10, minute=0, second=0, microsecond=0)
    a = "RT_CYCLE_ROUND_TRIP"
    nodes = ["A", "B", "C", "D", "E", "F", "G", "H"]
    rails = ["RTGS", "IMPS", "NEFT", "UPI", "IMPS", "NEFT", "RTGS", "NEFT"]
    amounts = [500000, 490000, 480000, 470000, 460000, 451000, 442000, 433000]
    edges = [
        _edge(f"{a}_{nodes[i]}", f"{a}_{nodes[(i+1) % 8]}", amounts[i], rails[i],
              base + timedelta(minutes=10 * i))
        for i in range(8)
    ]
    return edges


def _graph_cash_in_mule(amt: float) -> list[dict]:
    """
    Cash-like deposit → split to 4 ATM-like accounts.
    """
    base = _utcnow().replace(hour=10, minute=0, second=0, microsecond=0)
    a = "RT_CASH_IN_MULE"
    return [
        _edge(f"{a}_CASH_SOURCE", f"{a}_MULE",  200000, "NEFT", base),
        _edge(f"{a}_MULE",        f"{a}_ATM_1",  48000, "UPI",  base + timedelta(minutes=30)),
        _edge(f"{a}_MULE",        f"{a}_ATM_2",  47500, "UPI",  base + timedelta(minutes=35)),
        _edge(f"{a}_MULE",        f"{a}_ATM_3",  49000, "UPI",  base + timedelta(minutes=40)),
        _edge(f"{a}_MULE",        f"{a}_ATM_4",  48500, "UPI",  base + timedelta(minutes=45)),
    ]


def _graph_salary_mule(amt: float) -> list[dict]:
    """
    Salary receive → immediately forward to 4 destination accounts.
    """
    base = _utcnow().replace(hour=9, minute=0, second=0, microsecond=0)
    a = "RT_SALARY_MULE"
    return [
        _edge(f"{a}_EMPLOYER", f"{a}_MULE",   85000, "NEFT", base),
        _edge(f"{a}_MULE",     f"{a}_DEST_1", 25000, "UPI",  base + timedelta(minutes=5)),
        _edge(f"{a}_MULE",     f"{a}_DEST_2", 24000, "UPI",  base + timedelta(minutes=6)),
        _edge(f"{a}_MULE",     f"{a}_DEST_3", 20000, "IMPS", base + timedelta(minutes=8)),
        _edge(f"{a}_MULE",     f"{a}_DEST_4", 14000, "UPI",  base + timedelta(minutes=10)),
    ]


def _graph_low_slow_mule(amt: float) -> list[dict]:
    """
    5-day warmup (small txns) ending at now, then 1 large spike + immediate forward.
    """
    now = _utcnow()
    day = [now - timedelta(days=5 - i) for i in range(5)]
    a = "RT_LOW_SLOW_MULE"
    return [
        _edge(f"{a}_S1",         f"{a}_MULE",       3000, "UPI",  day[0].replace(hour=10, minute=0, second=0)),
        _edge(f"{a}_S2",         f"{a}_MULE",       4500, "UPI",  day[0].replace(hour=14, minute=0, second=0)),
        _edge(f"{a}_S3",         f"{a}_MULE",       2800, "IMPS", day[1].replace(hour=11, minute=0, second=0)),
        _edge(f"{a}_S4",         f"{a}_MULE",       5200, "UPI",  day[2].replace(hour=9,  minute=0, second=0)),
        _edge(f"{a}_S5",         f"{a}_MULE",       3900, "UPI",  day[3].replace(hour=15, minute=0, second=0)),
        _edge(f"{a}_MULE",       f"{a}_SMALL_1",    2000, "UPI",  day[3].replace(hour=15, minute=30, second=0)),
        _edge(f"{a}_BIG_SOURCE", f"{a}_MULE",     850000, "RTGS", day[4].replace(hour=2,  minute=0, second=0)),
        _edge(f"{a}_MULE",       f"{a}_COLLECTOR",840000, "UPI",  day[4].replace(hour=2,  minute=15, second=0)),
    ]


def _graph_romance_scam(amt: float) -> list[dict]:
    """
    Escalating transfers to same new VPA over 9 days, then layered out.
    """
    now = _utcnow()
    a = "RT_ROMANCE_SCAM"
    return [
        _edge(f"{a}_VICTIM", f"{a}_SCAMMER", 5000, "UPI", now - timedelta(days=8)),
        _edge(f"{a}_VICTIM", f"{a}_SCAMMER", 25000, "UPI", now - timedelta(days=6)),
        _edge(f"{a}_VICTIM", f"{a}_SCAMMER", 75000, "UPI", now - timedelta(days=4)),
        _edge(f"{a}_VICTIM", f"{a}_SCAMMER", 250000, "UPI", now - timedelta(days=2)),
        _edge(f"{a}_VICTIM", f"{a}_SCAMMER", 500000, "UPI", now),
        _edge(f"{a}_SCAMMER", f"{a}_LAYER_1", 480000, "IMPS", now + timedelta(minutes=10)),
        _edge(f"{a}_LAYER_1", f"{a}_LAYER_2", 465000, "NEFT", now + timedelta(minutes=25)),
        _edge(f"{a}_LAYER_2", f"{a}_COLLECTOR", 450000, "UPI", now + timedelta(minutes=40)),
    ]


def _graph_pig_butchering(amt: float) -> list[dict]:
    """
    3 small trust-building txns then 1 large exit + immediate crypto gateway forward + layering.
    """
    now = _utcnow()
    a = "RT_PIG_BUTCHERING"
    base_d10 = now
    return [
        _edge(f"{a}_VICTIM",   f"{a}_PLATFORM",    1000, "UPI",  now - timedelta(days=9)),
        _edge(f"{a}_VICTIM",   f"{a}_PLATFORM",    5000, "UPI",  now - timedelta(days=6)),
        _edge(f"{a}_VICTIM",   f"{a}_PLATFORM",   15000, "UPI",  now - timedelta(days=2)),
        _edge(f"{a}_VICTIM",   f"{a}_PLATFORM",  950000, "UPI",  base_d10),
        _edge(f"{a}_PLATFORM", f"{a}_CRYPTO_GW", 945000, "RTGS", base_d10 + timedelta(minutes=5)),
        _edge(f"{a}_CRYPTO_GW",f"{a}_LAYER_1",   920000, "UPI",  base_d10 + timedelta(minutes=20)),
        _edge(f"{a}_LAYER_1",  f"{a}_LAYER_2",   895000, "IMPS", base_d10 + timedelta(minutes=35)),
        _edge(f"{a}_LAYER_2",  f"{a}_FINAL",     870000, "NEFT", base_d10 + timedelta(minutes=50)),
    ]


def _graph_investment_fraud(amt: float) -> list[dict]:
    """
    Regular weekly deposits to "platform" then large final send + offshore forward.
    """
    now = _utcnow()
    a = "RT_INVESTMENT_FRAUD"
    return [
        _edge(f"{a}_VICTIM",   f"{a}_PLATFORM",  10000, "UPI",  now - timedelta(weeks=4)),
        _edge(f"{a}_VICTIM",   f"{a}_PLATFORM",  10000, "UPI",  now - timedelta(weeks=3)),
        _edge(f"{a}_VICTIM",   f"{a}_PLATFORM",  10000, "UPI",  now - timedelta(weeks=2)),
        _edge(f"{a}_VICTIM",   f"{a}_PLATFORM",  10000, "UPI",  now - timedelta(weeks=1)),
        _edge(f"{a}_VICTIM",   f"{a}_PLATFORM", 500000, "UPI",  now),
        _edge(f"{a}_PLATFORM", f"{a}_OFFSHORE", 535000, "RTGS", now + timedelta(hours=1)),
    ]


def _graph_account_takeover(amt: float) -> list[dict]:
    """
    1 immediate large UPI to new payee after device change + rapid secondary drain.
    """
    base = _utcnow().replace(second=0, microsecond=0)
    a = "RT_ACCOUNT_TAKEOVER"
    return [
        _edge(f"{a}_VICTIM", f"{a}_ATTACKER",   750000, "UPI", base),
        _edge(f"{a}_VICTIM", f"{a}_ATTACKER_2",  49000, "UPI", base + timedelta(minutes=3)),
        _edge(f"{a}_VICTIM", f"{a}_ATTACKER_3",  48500, "UPI", base + timedelta(minutes=4)),
    ]


def _graph_otp_fraud(amt: float) -> list[dict]:
    """
    3 failed small attempts then 1 large success + immediate mule forward and layering.
    """
    base = _utcnow().replace(second=0, microsecond=0)
    a = "RT_OTP_FRAUD"
    return [
        _edge(f"{a}_VICTIM",    f"{a}_FRAUD_ACC",   500, "UPI",  base),
        _edge(f"{a}_VICTIM",    f"{a}_FRAUD_ACC",   500, "UPI",  base + timedelta(minutes=2)),
        _edge(f"{a}_VICTIM",    f"{a}_FRAUD_ACC",   500, "UPI",  base + timedelta(minutes=4)),
        _edge(f"{a}_VICTIM",    f"{a}_FRAUD_ACC", 450000, "UPI",  base + timedelta(minutes=8)),
        _edge(f"{a}_FRAUD_ACC", f"{a}_MULE_1",    445000, "IMPS", base + timedelta(minutes=10)),
        _edge(f"{a}_MULE_1",    f"{a}_MULE_2",    432000, "NEFT", base + timedelta(minutes=22)),
        _edge(f"{a}_MULE_2",    f"{a}_COLLECTOR", 419000, "UPI",  base + timedelta(minutes=35)),
    ]


def _graph_sim_swap(amt: float) -> list[dict]:
    """
    Immediate high-value UPI after account reactivation across 3 mules, then consolidation.
    """
    base = _utcnow().replace(second=0, microsecond=0)
    a = "RT_SIM_SWAP"
    return [
        _edge(f"{a}_ATTACKER", f"{a}_MULE_1", 500000, "UPI",  base),
        _edge(f"{a}_ATTACKER", f"{a}_MULE_2", 300000, "UPI",  base + timedelta(minutes=2)),
        _edge(f"{a}_ATTACKER", f"{a}_MULE_3", 180000, "UPI",  base + timedelta(minutes=3)),
        _edge(f"{a}_MULE_1",   f"{a}_FINAL",  495000, "IMPS", base + timedelta(minutes=15)),
    ]


def _graph_ghost_node_cash(amt: float) -> list[dict]:
    """
    Receive → 18-hour silence → split send from different city.
    """
    now = _utcnow()
    a = "RT_GHOST_NODE_CASH"
    receive_time = now - timedelta(hours=18)
    return [
        _edge(f"{a}_SOURCE", f"{a}_GHOST",  350000, "NEFT", receive_time.replace(hour=10, minute=0, second=0)),
        _edge(f"{a}_GHOST",  f"{a}_DEST_1", 170000, "UPI",  now.replace(hour=4,  minute=0,  second=0)),
        _edge(f"{a}_GHOST",  f"{a}_DEST_2", 168000, "UPI",  now.replace(hour=4,  minute=5,  second=0)),
    ]


def _graph_merchant_terminal(amt: float) -> list[dict]:
    """
    Round-trip through POS terminal: ACC→POS→ACC→POS→COLLECTOR and secondary POS cycle.
    """
    base = _utcnow().replace(second=0, microsecond=0)
    a = "RT_MERCHANT_TERMINAL"
    return [
        _edge(f"{a}_ACC",            f"{a}_POS_TERMINAL_1", 85000, "UPI",  base),
        _edge(f"{a}_POS_TERMINAL_1", f"{a}_ACC",            83000, "UPI",  base + timedelta(minutes=5)),
        _edge(f"{a}_ACC",            f"{a}_POS_TERMINAL_1", 80000, "UPI",  base + timedelta(minutes=8)),
        _edge(f"{a}_POS_TERMINAL_1", f"{a}_COLLECTOR",      78000, "IMPS", base + timedelta(minutes=12)),
        _edge(f"{a}_ACC",            f"{a}_POS_TERMINAL_2", 76000, "UPI",  base + timedelta(minutes=18)),
        _edge(f"{a}_POS_TERMINAL_2", f"{a}_COLLECTOR",      74000, "NEFT", base + timedelta(minutes=25)),
    ]


def _graph_new_variant(amt: float) -> list[dict]:
    """
    Default 4-hop chain with mixed rails.
    """
    base = _utcnow().replace(second=0, microsecond=0)
    a = "RT_NEW_VARIANT"
    return [
        _edge(f"{a}_ORIGIN", f"{a}_HOP_1", 200000, "UPI",  base),
        _edge(f"{a}_HOP_1",  f"{a}_HOP_2", 195000, "IMPS", base + timedelta(minutes=15)),
        _edge(f"{a}_HOP_2",  f"{a}_HOP_3", 190000, "NEFT", base + timedelta(minutes=30)),
        _edge(f"{a}_HOP_3",  f"{a}_DEST",  185000, "UPI",  base + timedelta(minutes=45)),
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Dispatcher map
# ─────────────────────────────────────────────────────────────────────────────

_GRAPH_BUILDERS: dict[str, Any] = {
    "digital_arrest":    _graph_digital_arrest,
    "structuring":       _graph_structuring,
    "cycle_round_trip":  _graph_cycle_round_trip,
    "rapid_layering":    _graph_rapid_layering,
    "bipartite_mule":    _graph_bipartite_mule,
    "cash_in_mule":      _graph_cash_in_mule,
    "salary_mule":       _graph_salary_mule,
    "low_slow_mule":     _graph_low_slow_mule,
    "romance_scam":      _graph_romance_scam,
    "pig_butchering":    _graph_pig_butchering,
    "investment_fraud":  _graph_investment_fraud,
    "account_takeover":  _graph_account_takeover,
    "otp_fraud":         _graph_otp_fraud,
    "sim_swap":          _graph_sim_swap,
    "ghost_node_cash":   _graph_ghost_node_cash,
    "merchant_terminal": _graph_merchant_terminal,
}


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

_DEFAULT_AMOUNT = 150000.0


def evasion_to_tgep_graph(evasion: dict[str, Any], archetype: str) -> list[dict[str, Any]]:
    """Convert an evasion finding's feature vector into TGEP transaction edges."""
    evasion_vector = evasion.get("evasion_vector") or {}
    amt = float(evasion_vector.get("avg_txn_amount_30d", _DEFAULT_AMOUNT))
    builder = _GRAPH_BUILDERS.get(archetype, _graph_new_variant)
    return builder(amt)


def get_graph_for_mutation(
    mutation_type: str,
    evasion_vector: dict[str, float],
    archetype: str,
) -> list[dict[str, Any]]:
    """Return TGEP edges: uses pre-built graph for graph_bypass_ types, evasion_to_tgep_graph otherwise."""
    if mutation_type.startswith("graph_bypass_"):
        bypass_key = mutation_type.removeprefix("graph_bypass_")
        if bypass_key in VALID_BYPASS_TYPES:
            result = generate_tgep_bypass_graph(archetype, bypass_key)
            return result["edges"]
    return evasion_to_tgep_graph({"evasion_vector": evasion_vector}, archetype)
