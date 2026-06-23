"""
Graph Exporter — Convert Evasion Findings into TGEP Transaction Graph Format
=============================================================================
Converts any evasion finding (feature-level or graph-level) into a list of
realistic transaction edge dicts ready for TGEP's /transaction/manual endpoint.

Edge schema (per TGEP contract):
    {from_account, to_account, amount, payment_rail, timestamp}

Account name format: Realistic generic banking IDs
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
# Archetype-specific graph templates (Stealth sink-with-outflow variants)
# ─────────────────────────────────────────────────────────────────────────────

def _graph_digital_arrest(amt: float) -> list[dict]:
    base = _utcnow().replace(hour=10, minute=0, second=0, microsecond=0)
    c = "ACC104821"
    return [
        _edge("CORP441", c, 450000, "RTGS", base),
        _edge("CORP882", c, 680000, "RTGS", base + timedelta(days=1, hours=2)),
        _edge(c, "PAYROLL_VENDOR_111", 45000, "NEFT", base + timedelta(days=2, hours=1)),
        _edge(c, "UTIL_PROVIDER_112", 12000, "UPI", base + timedelta(days=2, hours=4)),
        _edge(c, "VENDOR_113", 28000, "IMPS", base + timedelta(days=2, hours=8)),
        _edge(c, "INSURER_114", 8000, "UPI", base + timedelta(days=3, hours=2)),
    ]

def _graph_structuring(amt: float) -> list[dict]:
    base = _utcnow().replace(hour=10, minute=0, second=0, microsecond=0)
    c = "ACC205934"
    return [
        _edge("CORP223", c, 48000, "NEFT", base),
        _edge("CORP224", c, 42000, "NEFT", base + timedelta(days=1, hours=3)),
        _edge("CORP225", c, 45000, "NEFT", base + timedelta(days=2, hours=1)),
        _edge("CORP226", c, 49000, "NEFT", base + timedelta(days=3, hours=4)),
        _edge(c, "VENDOR_221", 15000, "UPI", base + timedelta(days=4, hours=2)),
        _edge(c, "LANDLORD_222", 20000, "IMPS", base + timedelta(days=4, hours=5)),
        _edge(c, "VENDOR_223", 15000, "UPI", base + timedelta(days=5, hours=1)),
    ]

def _graph_rapid_layering(amt: float) -> list[dict]:
    base = _utcnow().replace(hour=10, minute=0, second=0, microsecond=0)
    c = "ACC301299"
    return [
        _edge("CORP311", c, 120000, "IMPS", base),
        _edge("CORP312", c, 180000, "IMPS", base + timedelta(hours=4)),
        _edge("CORP313", c, 150000, "IMPS", base + timedelta(hours=8)),
        _edge(c, "PAYROLL_VENDOR_314", 35000, "NEFT", base + timedelta(days=1, hours=2)),
        _edge(c, "SUBSCR_315", 5000, "UPI", base + timedelta(days=1, hours=5)),
        _edge(c, "VENDOR_316", 22000, "IMPS", base + timedelta(days=1, hours=9)),
        _edge(c, "INVEST_FUND_317", 18000, "RTGS", base + timedelta(days=2, hours=1)),
    ]

def _graph_bipartite_mule(amt: float) -> list[dict]:
    base = _utcnow().replace(hour=10, minute=0, second=0, microsecond=0)
    c = "ACC401822"
    return [
        _edge("CORP411", c, 85000, "UPI", base),
        _edge("CORP412", c, 92000, "UPI", base + timedelta(days=1)),
        _edge("CORP413", c, 88000, "UPI", base + timedelta(days=2)),
        _edge("CORP414", c, 95000, "UPI", base + timedelta(days=3)),
        _edge(c, "VENDOR_415", 40000, "IMPS", base + timedelta(days=4)),
        _edge(c, "UTIL_PROVIDER_416", 18000, "NEFT", base + timedelta(days=5)),
        _edge(c, "PAYROLL_VENDOR_417", 55000, "RTGS", base + timedelta(days=5, hours=6)),
        _edge(c, "LANDLORD_418", 25000, "UPI", base + timedelta(days=6)),
    ]

def _graph_cycle_round_trip(amt: float) -> list[dict]:
    base = _utcnow().replace(hour=10, minute=0, second=0, microsecond=0)
    c = "ACC501933"
    return [
        _edge("CORP511", c, 250000, "RTGS", base),
        _edge("CORP512", c, 280000, "RTGS", base + timedelta(days=1)),
        _edge(c, "INVEST_FUND_513", 45000, "NEFT", base + timedelta(days=2)),
        _edge(c, "PAYROLL_VENDOR_514", 38000, "IMPS", base + timedelta(days=3)),
        _edge(c, "VENDOR_515", 22000, "UPI", base + timedelta(days=4)),
    ]

def _graph_cash_in_mule(amt: float) -> list[dict]:
    base = _utcnow().replace(hour=10, minute=0, second=0, microsecond=0)
    c = "ACC601144"
    return [
        _edge("CORP611", c, 150000, "UPI", base),
        _edge("CORP612", c, 280000, "NEFT", base + timedelta(days=1)),
        _edge("CORP613", c, 120000, "IMPS", base + timedelta(days=1, hours=12)),
        _edge(c, "VENDOR_614", 30000, "UPI", base + timedelta(days=2)),
        _edge(c, "VENDOR_615", 30000, "UPI", base + timedelta(days=2, hours=3)),
        _edge(c, "VENDOR_616", 30000, "UPI", base + timedelta(days=2, hours=6)),
        _edge(c, "PAYROLL_VENDOR_617", 25000, "NEFT", base + timedelta(days=3)),
    ]

def _graph_salary_mule(amt: float) -> list[dict]:
    base = _utcnow().replace(hour=10, minute=0, second=0, microsecond=0)
    c = "ACC701255"
    return [
        _edge("CORP711", c, 85000, "NEFT", base),
        _edge("CORP712", c, 25000, "IMPS", base + timedelta(hours=6)),
        _edge(c, "LANDLORD_713", 18000, "UPI", base + timedelta(days=1)),
        _edge(c, "UTIL_PROVIDER_714", 8000, "UPI", base + timedelta(days=1, hours=5)),
        _edge(c, "SUBSCR_715", 3000, "UPI", base + timedelta(days=1, hours=10)),
        _edge(c, "VENDOR_716", 12000, "IMPS", base + timedelta(days=2)),
    ]

def _graph_low_slow_mule(amt: float) -> list[dict]:
    base = _utcnow().replace(hour=10, minute=0, second=0, microsecond=0) - timedelta(days=30)
    c = "ACC801366"
    return [
        _edge("CORP811", c, 2000, "UPI", base),
        _edge("CORP812", c, 3500, "UPI", base + timedelta(days=7)),
        _edge("CORP813", c, 5000, "UPI", base + timedelta(days=14)),
        _edge("CORP814", c, 8000, "UPI", base + timedelta(days=21)),
        _edge("CORP815", c, 4000, "UPI", base + timedelta(days=28)),
        _edge(c, "VENDOR_816", 3000, "IMPS", base + timedelta(days=29)),
        _edge(c, "VENDOR_817", 3000, "UPI", base + timedelta(days=30)),
    ]

def _graph_romance_scam(amt: float) -> list[dict]:
    base = _utcnow().replace(hour=10, minute=0, second=0, microsecond=0)
    c = "ACC901477"
    return [
        _edge("CORP911", c, 5000, "UPI", base),
        _edge("CORP912", c, 25000, "UPI", base + timedelta(days=3)),
        _edge("CORP913", c, 75000, "UPI", base + timedelta(days=6)),
        _edge(c, "VENDOR_914", 8000, "IMPS", base + timedelta(days=7)),
        _edge(c, "SUBSCR_915", 5000, "UPI", base + timedelta(days=8)),
        _edge(c, "UTIL_PROVIDER_916", 12000, "NEFT", base + timedelta(days=9)),
    ]

def _graph_pig_butchering(amt: float) -> list[dict]:
    base = _utcnow().replace(hour=10, minute=0, second=0, microsecond=0)
    c = "ACC120588"
    return [
        _edge("CORP121", c, 1000, "UPI", base),
        _edge("CORP122", c, 5000, "UPI", base + timedelta(days=2)),
        _edge("CORP123", c, 15000, "UPI", base + timedelta(days=5)),
        _edge("CORP124", c, 50000, "UPI", base + timedelta(days=8)),
        _edge(c, "VENDOR_125", 8000, "IMPS", base + timedelta(days=9)),
        _edge(c, "INSURER_126", 12000, "NEFT", base + timedelta(days=9, hours=12)),
        _edge(c, "VENDOR_127", 8000, "UPI", base + timedelta(days=10)),
    ]

def _graph_investment_fraud(amt: float) -> list[dict]:
    base = _utcnow().replace(hour=10, minute=0, second=0, microsecond=0) - timedelta(days=35)
    c = "ACC230699"
    return [
        _edge("CORP231", c, 10000, "UPI", base),
        _edge("CORP232", c, 10000, "UPI", base + timedelta(days=7)),
        _edge("CORP233", c, 10000, "UPI", base + timedelta(days=14)),
        _edge("CORP234", c, 10000, "UPI", base + timedelta(days=21)),
        _edge("CORP235", c, 10000, "UPI", base + timedelta(days=28)),
        _edge(c, "VENDOR_236", 15000, "IMPS", base + timedelta(days=30)),
        _edge(c, "UTIL_PROVIDER_237", 8000, "NEFT", base + timedelta(days=32)),
        _edge(c, "PAYROLL_VENDOR_238", 20000, "RTGS", base + timedelta(days=35)),
    ]

def _graph_account_takeover(amt: float) -> list[dict]:
    base = _utcnow().replace(hour=10, minute=0, second=0, microsecond=0)
    c = "ACC340711"
    return [
        _edge("CORP341", c, 750000, "RTGS", base),
        _edge("CORP342", c, 180000, "UPI", base + timedelta(hours=2)),
        _edge(c, "VENDOR_343", 25000, "IMPS", base + timedelta(hours=4)),
        _edge(c, "VENDOR_344", 25000, "NEFT", base + timedelta(hours=6)),
        _edge(c, "VENDOR_345", 25000, "UPI", base + timedelta(hours=8)),
        _edge(c, "LANDLORD_346", 18000, "RTGS", base + timedelta(hours=10)),
        _edge(c, "PAYROLL_VENDOR_347", 30000, "IMPS", base + timedelta(hours=20)),
    ]

def _graph_otp_fraud(amt: float) -> list[dict]:
    base = _utcnow().replace(hour=10, minute=0, second=0, microsecond=0)
    c = "ACC450822"
    return [
        _edge("CORP451", c, 500, "UPI", base),
        _edge("CORP452", c, 500, "UPI", base + timedelta(minutes=10)),
        _edge("CORP453", c, 500, "UPI", base + timedelta(minutes=20)),
        _edge("CORP454", c, 450000, "UPI", base + timedelta(minutes=30)),
        _edge(c, "PAYROLL_VENDOR_455", 35000, "NEFT", base + timedelta(minutes=50)),
        _edge(c, "VENDOR_456", 28000, "IMPS", base + timedelta(hours=2)),
        _edge(c, "UTIL_PROVIDER_457", 15000, "UPI", base + timedelta(hours=5)),
    ]

def _graph_sim_swap(amt: float) -> list[dict]:
    base = _utcnow().replace(hour=22, minute=0, second=0, microsecond=0)
    c = "ACC560933"
    return [
        _edge("CORP561", c, 450000, "UPI", base),
        _edge("CORP562", c, 300000, "UPI", base + timedelta(hours=1)),
        _edge(c, "VENDOR_563", 45000, "IMPS", base + timedelta(hours=3)),
        _edge(c, "INVEST_FUND_564", 30000, "RTGS", base + timedelta(hours=6)),
        _edge(c, "PAYROLL_VENDOR_565", 25000, "NEFT", base + timedelta(hours=9)),
    ]

def _graph_ghost_node_cash(amt: float) -> list[dict]:
    base = _utcnow().replace(hour=10, minute=0, second=0, microsecond=0)
    c = "ACC670144"
    return [
        _edge("CORP671", c, 350000, "NEFT", base),
        _edge("CORP672", c, 180000, "NEFT", base + timedelta(hours=18)),
        _edge(c, "VENDOR_673", 35000, "IMPS", base + timedelta(days=1)),
        _edge(c, "VENDOR_674", 35000, "UPI", base + timedelta(days=1, hours=6)),
        _edge(c, "UTIL_PROVIDER_675", 18000, "UPI", base + timedelta(days=2)),
    ]

def _graph_merchant_terminal(amt: float) -> list[dict]:
    base = _utcnow().replace(hour=10, minute=0, second=0, microsecond=0)
    c = "ACC780255"
    return [
        _edge("CORP781", c, 85000, "UPI", base),
        _edge("CORP782", c, 76000, "UPI", base + timedelta(hours=4)),
        _edge(c, "VENDOR_783", 28000, "IMPS", base + timedelta(days=1)),
        _edge(c, "PAYROLL_VENDOR_784", 32000, "NEFT", base + timedelta(days=1, hours=12)),
        _edge(c, "UTIL_PROVIDER_785", 15000, "UPI", base + timedelta(days=2)),
        _edge(c, "SUBSCR_786", 8000, "UPI", base + timedelta(days=3)),
    ]

def _graph_new_variant(amt: float) -> list[dict]:
    base = _utcnow().replace(hour=10, minute=0, second=0, microsecond=0)
    c = "ACC890366"
    return [
        _edge("CORP891", c, 150000, "UPI", base),
        _edge("CORP892", c, 200000, "NEFT", base + timedelta(days=1)),
        _edge(c, "PAYROLL_VENDOR_893", 35000, "RTGS", base + timedelta(days=2)),
        _edge(c, "VENDOR_894", 22000, "IMPS", base + timedelta(days=2, hours=8)),
        _edge(c, "UTIL_PROVIDER_895", 12000, "UPI", base + timedelta(days=3)),
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
