"""
Graph Exporter — Convert Evasion Findings into TGEP Transaction Graph Format
=============================================================================
Converts any evasion finding (feature-level or graph-level) into a list of
realistic transaction edge dicts ready for TGEP's /transaction/manual endpoint.

Edge schema (per TGEP contract):
    {from_account, to_account, amount, payment_rail, timestamp}

Confirmed evasion structure (tested 2026-06-05, UNDETECTED):
    3 institutional inflows → 1 central account → 2 small outflows max
    - Max 5 accounts total
    - Outflow ≤ 15% of total inflow
    - Fan-out capped at 2 to evade TGEP Fan-Out Network detector

Account name format: Realistic generic banking IDs
Timestamp format: "2026-06-17T10:00:00" (no timezone suffix, UTC)
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from app.engines.graph_adversary import VALID_BYPASS_TYPES, generate_tgep_bypass_graph


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
# Structure: 3 inflows → 1 central acc → max 2 outflows (≤15% of inflow total)
# ─────────────────────────────────────────────────────────────────────────────

def _graph_digital_arrest(amt: float) -> list[dict]:
    # Total inflow: 1130000. Outflow: 57000 (5.0%)
    base = _utcnow().replace(hour=10, minute=0, second=0, microsecond=0)
    c = "ACC104821"
    return [
        _edge("CORP441",  c,                450000, "RTGS", base),
        _edge("CORP882",  c,                380000, "RTGS", base + timedelta(days=1, hours=2)),
        _edge("CORP219",  c,                300000, "NEFT", base + timedelta(days=2, hours=1)),
        _edge(c, "PAYROLL_VENDOR_111",  45000, "NEFT", base + timedelta(days=3, hours=1)),
        _edge(c, "UTIL_PROVIDER_112",   12000, "UPI",  base + timedelta(days=3, hours=5)),
    ]

def _graph_structuring(amt: float) -> list[dict]:
    # Total inflow: 135000. Outflow: 18000 (13.3%)
    base = _utcnow().replace(hour=10, minute=0, second=0, microsecond=0)
    c = "ACC205934"
    return [
        _edge("CORP223",  c,                48000, "NEFT", base),
        _edge("CORP224",  c,                42000, "NEFT", base + timedelta(days=1, hours=3)),
        _edge("CORP225",  c,                45000, "NEFT", base + timedelta(days=2, hours=1)),
        _edge(c, "PAYROLL_VENDOR_221",  12000, "NEFT", base + timedelta(days=3, hours=2)),
        _edge(c, "UTIL_PROVIDER_222",    6000, "UPI",  base + timedelta(days=3, hours=6)),
    ]

def _graph_rapid_layering(amt: float) -> list[dict]:
    # Total inflow: 450000. Outflow: 55000 (12.2%)
    base = _utcnow().replace(hour=10, minute=0, second=0, microsecond=0)
    c = "ACC301299"
    return [
        _edge("CORP311",  c,                120000, "IMPS", base),
        _edge("CORP312",  c,                180000, "RTGS", base + timedelta(hours=6)),
        _edge("CORP313",  c,                150000, "NEFT", base + timedelta(hours=12)),
        _edge(c, "PAYROLL_VENDOR_314",  40000, "NEFT", base + timedelta(days=1, hours=2)),
        _edge(c, "UTIL_PROVIDER_315",   15000, "UPI",  base + timedelta(days=1, hours=8)),
    ]

def _graph_bipartite_mule(amt: float) -> list[dict]:
    # Total inflow: 265000. Outflow: 30000 (11.3%)
    base = _utcnow().replace(hour=10, minute=0, second=0, microsecond=0)
    c = "ACC401822"
    return [
        _edge("CORP411",  c,                85000, "UPI",  base),
        _edge("CORP412",  c,                92000, "IMPS", base + timedelta(days=1)),
        _edge("CORP413",  c,                88000, "NEFT", base + timedelta(days=2)),
        _edge(c, "PAYROLL_VENDOR_415",  22000, "NEFT", base + timedelta(days=3)),
        _edge(c, "UTIL_PROVIDER_416",    8000, "UPI",  base + timedelta(days=3, hours=8)),
    ]

def _graph_cycle_round_trip(amt: float) -> list[dict]:
    # Total inflow: 780000. Outflow: 65000 (8.3%)
    base = _utcnow().replace(hour=10, minute=0, second=0, microsecond=0)
    c = "ACC501933"
    return [
        _edge("CORP511",  c,                250000, "RTGS", base),
        _edge("CORP512",  c,                280000, "RTGS", base + timedelta(days=1)),
        _edge("CORP513",  c,                250000, "NEFT", base + timedelta(days=2)),
        _edge(c, "PAYROLL_VENDOR_514",  45000, "NEFT", base + timedelta(days=3)),
        _edge(c, "UTIL_PROVIDER_515",   20000, "UPI",  base + timedelta(days=3, hours=6)),
    ]

def _graph_cash_in_mule(amt: float) -> list[dict]:
    # Total inflow: 550000. Outflow: 55000 (10.0%)
    base = _utcnow().replace(hour=10, minute=0, second=0, microsecond=0)
    c = "ACC601144"
    return [
        _edge("CORP611",  c,                150000, "UPI",  base),
        _edge("CORP612",  c,                280000, "NEFT", base + timedelta(days=1)),
        _edge("CORP613",  c,                120000, "IMPS", base + timedelta(days=1, hours=12)),
        _edge(c, "PAYROLL_VENDOR_614",  40000, "NEFT", base + timedelta(days=2)),
        _edge(c, "UTIL_PROVIDER_615",   15000, "UPI",  base + timedelta(days=2, hours=6)),
    ]

def _graph_salary_mule(amt: float) -> list[dict]:
    # Total inflow: 195000. Outflow: 25000 (12.8%)
    base = _utcnow().replace(hour=10, minute=0, second=0, microsecond=0)
    c = "ACC701255"
    return [
        _edge("CORP711",  c,                85000, "NEFT", base),
        _edge("CORP712",  c,                65000, "IMPS", base + timedelta(hours=6)),
        _edge("CORP713",  c,                45000, "UPI",  base + timedelta(hours=12)),
        _edge(c, "PAYROLL_VENDOR_714",  18000, "NEFT", base + timedelta(days=1)),
        _edge(c, "UTIL_PROVIDER_715",    7000, "UPI",  base + timedelta(days=1, hours=8)),
    ]

def _graph_low_slow_mule(amt: float) -> list[dict]:
    # Total inflow: 22500. Outflow: 3200 (14.2%)
    base = _utcnow().replace(hour=10, minute=0, second=0, microsecond=0) - timedelta(days=30)
    c = "ACC801366"
    return [
        _edge("CORP811",  c,                 8000, "UPI",  base),
        _edge("CORP812",  c,                 7500, "UPI",  base + timedelta(days=10)),
        _edge("CORP813",  c,                 7000, "UPI",  base + timedelta(days=20)),
        _edge(c, "PAYROLL_VENDOR_816",   2500, "NEFT", base + timedelta(days=25)),
        _edge(c, "UTIL_PROVIDER_817",     700, "UPI",  base + timedelta(days=28)),
    ]

def _graph_romance_scam(amt: float) -> list[dict]:
    # Total inflow: 105000. Outflow: 13000 (12.4%)
    base = _utcnow().replace(hour=10, minute=0, second=0, microsecond=0)
    c = "ACC901477"
    return [
        _edge("CORP911",  c,                25000, "UPI",  base),
        _edge("CORP912",  c,                55000, "UPI",  base + timedelta(days=3)),
        _edge("CORP913",  c,                25000, "IMPS", base + timedelta(days=6)),
        _edge(c, "PAYROLL_VENDOR_914",  10000, "NEFT", base + timedelta(days=7)),
        _edge(c, "UTIL_PROVIDER_915",    3000, "UPI",  base + timedelta(days=8)),
    ]

def _graph_pig_butchering(amt: float) -> list[dict]:
    # Total inflow: 71000. Outflow: 9500 (13.4%)
    base = _utcnow().replace(hour=10, minute=0, second=0, microsecond=0)
    c = "ACC120588"
    return [
        _edge("CORP121",  c,                20000, "UPI",  base),
        _edge("CORP122",  c,                31000, "UPI",  base + timedelta(days=3)),
        _edge("CORP123",  c,                20000, "IMPS", base + timedelta(days=6)),
        _edge(c, "PAYROLL_VENDOR_124",   7000, "NEFT", base + timedelta(days=7)),
        _edge(c, "UTIL_PROVIDER_125",    2500, "UPI",  base + timedelta(days=8)),
    ]

def _graph_investment_fraud(amt: float) -> list[dict]:
    # Total inflow: 60000. Outflow: 8000 (13.3%)
    base = _utcnow().replace(hour=10, minute=0, second=0, microsecond=0) - timedelta(days=35)
    c = "ACC230699"
    return [
        _edge("CORP231",  c,                20000, "UPI",  base),
        _edge("CORP232",  c,                22000, "UPI",  base + timedelta(days=14)),
        _edge("CORP233",  c,                18000, "NEFT", base + timedelta(days=28)),
        _edge(c, "PAYROLL_VENDOR_234",   6000, "NEFT", base + timedelta(days=30)),
        _edge(c, "UTIL_PROVIDER_235",    2000, "UPI",  base + timedelta(days=32)),
    ]

def _graph_account_takeover(amt: float) -> list[dict]:
    # Total inflow: 930000. Outflow: 55000 (5.9%)
    base = _utcnow().replace(hour=10, minute=0, second=0, microsecond=0)
    c = "ACC340711"
    return [
        _edge("CORP341",  c,                750000, "RTGS", base),
        _edge("CORP342",  c,                100000, "NEFT", base + timedelta(hours=2)),
        _edge("CORP343",  c,                 80000, "UPI",  base + timedelta(hours=4)),
        _edge(c, "PAYROLL_VENDOR_344",   40000, "NEFT", base + timedelta(hours=8)),
        _edge(c, "UTIL_PROVIDER_345",    15000, "UPI",  base + timedelta(hours=16)),
    ]

def _graph_otp_fraud(amt: float) -> list[dict]:
    # Total inflow: 450000. Outflow: 55000 (12.2%)
    base = _utcnow().replace(hour=10, minute=0, second=0, microsecond=0)
    c = "ACC450822"
    return [
        _edge("CORP451",  c,                200000, "UPI",  base),
        _edge("CORP452",  c,                150000, "IMPS", base + timedelta(minutes=30)),
        _edge("CORP453",  c,                100000, "NEFT", base + timedelta(hours=1)),
        _edge(c, "PAYROLL_VENDOR_454",   40000, "NEFT", base + timedelta(hours=3)),
        _edge(c, "UTIL_PROVIDER_455",    15000, "UPI",  base + timedelta(hours=6)),
    ]

def _graph_sim_swap(amt: float) -> list[dict]:
    # Total inflow: 750000. Outflow: 58000 (7.7%)
    base = _utcnow().replace(hour=22, minute=0, second=0, microsecond=0)
    c = "ACC560933"
    return [
        _edge("CORP561",  c,                450000, "UPI",  base),
        _edge("CORP562",  c,                200000, "RTGS", base + timedelta(hours=1)),
        _edge("CORP563",  c,                100000, "NEFT", base + timedelta(hours=2)),
        _edge(c, "PAYROLL_VENDOR_564",   45000, "NEFT", base + timedelta(hours=5)),
        _edge(c, "UTIL_PROVIDER_565",    13000, "UPI",  base + timedelta(hours=9)),
    ]

def _graph_ghost_node_cash(amt: float) -> list[dict]:
    # Total inflow: 530000. Outflow: 53000 (10.0%)
    base = _utcnow().replace(hour=10, minute=0, second=0, microsecond=0)
    c = "ACC670144"
    return [
        _edge("CORP671",  c,                350000, "NEFT", base),
        _edge("CORP672",  c,                110000, "RTGS", base + timedelta(hours=8)),
        _edge("CORP673",  c,                 70000, "IMPS", base + timedelta(hours=18)),
        _edge(c, "PAYROLL_VENDOR_674",   40000, "NEFT", base + timedelta(days=1)),
        _edge(c, "UTIL_PROVIDER_675",    13000, "UPI",  base + timedelta(days=1, hours=8)),
    ]

def _graph_merchant_terminal(amt: float) -> list[dict]:
    # Total inflow: 241000. Outflow: 28000 (11.6%)
    base = _utcnow().replace(hour=10, minute=0, second=0, microsecond=0)
    c = "ACC780255"
    return [
        _edge("CORP781",  c,                85000, "UPI",  base),
        _edge("CORP782",  c,                96000, "IMPS", base + timedelta(hours=4)),
        _edge("CORP783",  c,                60000, "NEFT", base + timedelta(hours=8)),
        _edge(c, "PAYROLL_VENDOR_784",   20000, "NEFT", base + timedelta(days=1)),
        _edge(c, "UTIL_PROVIDER_785",     8000, "UPI",  base + timedelta(days=1, hours=6)),
    ]

def _graph_new_variant(amt: float) -> list[dict]:
    # Total inflow: 350000. Outflow: 35000 (10.0%)
    base = _utcnow().replace(hour=10, minute=0, second=0, microsecond=0)
    c = "ACC890366"
    return [
        _edge("CORP891",  c,                150000, "UPI",  base),
        _edge("CORP892",  c,                120000, "NEFT", base + timedelta(days=1)),
        _edge("CORP893",  c,                 80000, "RTGS", base + timedelta(days=2)),
        _edge(c, "PAYROLL_VENDOR_894",   25000, "NEFT", base + timedelta(days=3)),
        _edge(c, "UTIL_PROVIDER_895",    10000, "UPI",  base + timedelta(days=3, hours=8)),
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
