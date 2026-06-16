"""
Graph Adversary — Synthesise Subgraphs That Bypass Blue Team's 5 Hard Gates
=============================================================================
Generates synthetic transaction subgraphs for each gate bypass strategy.

Gates and bypass strategies:
  cycle           → 9-hop path (Blue Team checks 2–8 hops only → outside range)
  sink            → add small outflow txns to reduce sink_score below trigger threshold
  bipartite       → split 7 senders into 2 batches of 4+3 (density drops below 0.7)
  cash_mule_sink  → insert 48h digital activity between receive and ATM withdrawal
  merchant_terminal → route through 2 POS terminals (not round-trip on 1)

Returns:
    {
        gate_name:         str,
        bypass_strategy:   str,
        synthetic_subgraph: dict,   # nodes, edges, metadata
        expected_to_trigger: bool,  # False = bypass is expected to avoid gate
    }
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from app.utils.audit_logger import get_logger
from app.engines.tgep_bypass_graphs import generate_tgep_bypass_graph  # noqa: F401 re-export

log = get_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Gate names
# ─────────────────────────────────────────────────────────────────────────────

VALID_GATES = frozenset(
    {"cycle", "sink", "bipartite", "cash_mule_sink", "merchant_terminal"}
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _node(node_id: str, node_type: str, **attrs: Any) -> dict[str, Any]:
    return {"id": node_id, "type": node_type, **attrs}


def _edge(
    src: str,
    dst: str,
    amount: float,
    ts: datetime,
    edge_type: str = "transfer",
    **attrs: Any,
) -> dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "src": src,
        "dst": dst,
        "amount": amount,
        "timestamp": ts.isoformat(),
        "type": edge_type,
        **attrs,
    }


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ─────────────────────────────────────────────────────────────────────────────
# Gate bypass implementations
# ─────────────────────────────────────────────────────────────────────────────


def _bypass_cycle(transaction_data: dict[str, Any]) -> dict[str, Any]:
    """
    Cycle gate bypass: insert 2 intermediary nodes so the path from A→C
    spans 9 hops (Blue Team's cycle detector checks 2–8 hops only).

    Graph: A → I1 → I2 → I3 → I4 → I5 → I6 → I7 → I8 → C
    That is 9 edges = 9 hops, just outside the 2–8 detection window.
    """
    base_time = _now()
    node_a = "node_A"
    node_c = "node_C"
    intermediaries = [f"intermediary_{i}" for i in range(1, 9)]  # 8 nodes

    nodes = (
        [_node(node_a, "account", role="originator")]
        + [_node(n, "account", role="intermediary") for n in intermediaries]
        + [_node(node_c, "account", role="recipient")]
    )

    # Create 9-hop chain: A → I1 → I2 → … → I8 → C
    chain = [node_a] + intermediaries + [node_c]
    edges = []
    amount = transaction_data.get("amount", 45000.0)
    for hop, (src, dst) in enumerate(zip(chain[:-1], chain[1:])):
        edges.append(
            _edge(
                src=src,
                dst=dst,
                amount=amount * (0.99**hop),  # tiny decay per hop
                ts=base_time + timedelta(minutes=hop * 2),
                hop=hop + 1,
            )
        )

    return {
        "gate_name": "cycle",
        "bypass_strategy": (
            "Insert 8 intermediary nodes so the A→C path spans 9 hops. "
            "Blue Team cycle detector checks 2–8 hops only; 9 hops is outside the window."
        ),
        "synthetic_subgraph": {
            "nodes": nodes,
            "edges": edges,
            "total_hops": len(edges),
            "detection_window": "2-8",
            "bypass_hops": 9,
        },
        "expected_to_trigger": False,
        "gate_threshold": {"min_hops": 2, "max_hops": 8},
    }


def _bypass_sink(transaction_data: dict[str, Any]) -> dict[str, Any]:
    """
    Sink gate bypass: add small outflow transactions to reduce
    sink_score = retention × inflow_concentration below trigger threshold.

    Strategy: introduce 5 small legitimate-looking outflows from the sink node.
    This lowers retention and inflow_concentration, pushing sink_score below 0.6.
    """
    base_time = _now()
    sink_node = "sink_account"
    inflow_source = "inflow_source"
    outflow_targets = [f"outflow_target_{i}" for i in range(1, 6)]

    inflow_amount = transaction_data.get("amount", 80000.0)
    outflow_per_target = inflow_amount * 0.15  # 5 × 15% = 75% dispersed

    nodes = (
        [_node(inflow_source, "account", role="sender")]
        + [_node(sink_node, "account", role="sink_candidate")]
        + [_node(t, "account", role="outflow_recipient") for t in outflow_targets]
    )

    edges = [
        _edge(inflow_source, sink_node, inflow_amount, base_time, label="main_inflow"),
    ] + [
        _edge(
            sink_node,
            target,
            outflow_per_target,
            base_time + timedelta(hours=i + 1),
            label="dispersal_outflow",
        )
        for i, target in enumerate(outflow_targets)
    ]

    estimated_retention = 1.0 - (outflow_per_target * 5 / inflow_amount)
    estimated_sink_score = estimated_retention * 0.5  # inflow_concentration drops

    return {
        "gate_name": "sink",
        "bypass_strategy": (
            "Add 5 small dispersal outflows (15% each) from the sink node immediately "
            "after the main inflow. This reduces retention to ~0.25 and inflow_concentration, "
            "pushing sink_score below the 0.6 trigger threshold."
        ),
        "synthetic_subgraph": {
            "nodes": nodes,
            "edges": edges,
            "estimated_retention": round(estimated_retention, 3),
            "estimated_sink_score": round(estimated_sink_score, 3),
            "trigger_threshold": 0.6,
        },
        "expected_to_trigger": False,
        "gate_threshold": {"sink_score_min": 0.6},
    }


def _bypass_bipartite(transaction_data: dict[str, Any]) -> dict[str, Any]:
    """
    Bipartite gate bypass: split 7 senders into 2 batches (4 + 3) sending to 2
    different recipient clusters. Bipartite density of each sub-graph drops below 0.7.

    Original: 7 senders → 1 recipient  (density = 7/7 = 1.0 → triggers gate)
    Bypass:   4 senders → recipient_A  (density = 4/4 = 1.0 / 7 ≈ 0.57 per cluster)
              3 senders → recipient_B  (density = 3/3 = 1.0 / 7 ≈ 0.43 per cluster)

    Combined effective bipartite density = (4 + 3) / (4×1 + 3×1) = below 0.7 trigger.
    """
    base_time = _now()
    senders = [f"sender_{i}" for i in range(1, 8)]  # 7 senders
    recipient_a = "recipient_A"
    recipient_b = "recipient_B"

    batch_a = senders[:4]
    batch_b = senders[4:]

    amount = transaction_data.get("amount", 10000.0)

    nodes = (
        [_node(s, "account", role="sender") for s in senders]
        + [_node(recipient_a, "account", role="recipient", batch="A")]
        + [_node(recipient_b, "account", role="recipient", batch="B")]
    )

    edges = [
        _edge(s, recipient_a, amount, base_time + timedelta(minutes=i), batch="A")
        for i, s in enumerate(batch_a)
    ] + [
        _edge(s, recipient_b, amount, base_time + timedelta(minutes=i + 10), batch="B")
        for i, s in enumerate(batch_b)
    ]

    # Bipartite density per cluster
    density_a = len(batch_a) / (len(batch_a) * 1)  # 1.0 within cluster — but cluster is smaller
    density_b = len(batch_b) / (len(batch_b) * 1)
    # Effective combined density across the full bipartite graph
    effective_density = (len(batch_a) + len(batch_b)) / (
        len(senders) * 2  # 2 recipients
    )

    return {
        "gate_name": "bipartite",
        "bypass_strategy": (
            "Split 7 senders into two batches (4+3) targeting 2 different recipient accounts. "
            "Effective combined bipartite density = 7/14 = 0.5, below the 0.7 trigger threshold."
        ),
        "synthetic_subgraph": {
            "nodes": nodes,
            "edges": edges,
            "batch_a_senders": len(batch_a),
            "batch_b_senders": len(batch_b),
            "effective_bipartite_density": round(effective_density, 3),
            "trigger_threshold": 0.7,
        },
        "expected_to_trigger": False,
        "gate_threshold": {"bipartite_density_min": 0.7},
    }


def _bypass_cash_mule_sink(transaction_data: dict[str, Any]) -> dict[str, Any]:
    """
    Cash mule sink bypass: insert 48h of digital activity between the receive
    event and the ATM withdrawal. Blue Team's dormancy pattern checker requires
    the withdrawal to follow the receive with no intervening digital activity.
    """
    base_time = _now()
    mule_account = "mule_account"
    sender = "sender_account"
    atm = "atm_terminal"
    digital_merchants = [f"digital_merchant_{i}" for i in range(1, 4)]

    receive_time = base_time
    digital_activity_start = base_time + timedelta(hours=2)
    atm_time = base_time + timedelta(hours=50)  # 50h after receive (> 48h buffer)

    amount = transaction_data.get("amount", 50000.0)

    nodes = (
        [_node(sender, "account", role="sender")]
        + [_node(mule_account, "account", role="mule")]
        + [_node(atm, "atm", role="cash_out")]
        + [_node(m, "merchant", role="digital_activity") for m in digital_merchants]
    )

    edges = [
        _edge(sender, mule_account, amount, receive_time, label="receive"),
    ] + [
        _edge(
            mule_account,
            m,
            amount * 0.03,
            digital_activity_start + timedelta(hours=i * 12),
            edge_type="digital_payment",
            label="digital_activity",
        )
        for i, m in enumerate(digital_merchants)
    ] + [
        _edge(mule_account, atm, amount * 0.85, atm_time, edge_type="atm_withdrawal", label="cash_out"),
    ]

    return {
        "gate_name": "cash_mule_sink",
        "bypass_strategy": (
            "Insert 3 small digital payments across 48h between the receive event and ATM withdrawal. "
            "Blue Team dormancy pattern requires direct receive→ATM with no digital activity; "
            "the 48h digital buffer breaks this pattern and avoids the gate."
        ),
        "synthetic_subgraph": {
            "nodes": nodes,
            "edges": edges,
            "receive_to_atm_hours": 50,
            "digital_activity_transactions": len(digital_merchants),
            "dormancy_break_threshold_hours": 48,
        },
        "expected_to_trigger": False,
        "gate_threshold": {"dormancy_pattern": "direct_receive_to_atm_no_digital"},
    }


def _bypass_merchant_terminal(transaction_data: dict[str, Any]) -> dict[str, Any]:
    """
    Merchant terminal bypass: route through 2 separate POS terminals instead of
    round-trip through a single terminal. Blue Team's merchant_terminal gate
    detects the round-trip pattern on a single terminal.
    """
    base_time = _now()
    account = "source_account"
    pos_1 = "pos_terminal_1"
    pos_2 = "pos_terminal_2"
    merchant_1 = "merchant_account_1"
    merchant_2 = "merchant_account_2"

    amount = transaction_data.get("amount", 15000.0)

    nodes = [
        _node(account, "account", role="source"),
        _node(pos_1, "pos_terminal", terminal_id="T001"),
        _node(pos_2, "pos_terminal", terminal_id="T002"),
        _node(merchant_1, "merchant", role="recipient_1"),
        _node(merchant_2, "merchant", role="recipient_2"),
    ]

    edges = [
        _edge(
            account, pos_1, amount * 0.5,
            base_time,
            edge_type="pos_payment",
            terminal="T001",
        ),
        _edge(
            pos_1, merchant_1, amount * 0.5,
            base_time + timedelta(minutes=5),
            edge_type="settlement",
            terminal="T001",
        ),
        _edge(
            account, pos_2, amount * 0.5,
            base_time + timedelta(hours=2),
            edge_type="pos_payment",
            terminal="T002",
        ),
        _edge(
            pos_2, merchant_2, amount * 0.5,
            base_time + timedelta(hours=2, minutes=5),
            edge_type="settlement",
            terminal="T002",
        ),
    ]

    return {
        "gate_name": "merchant_terminal",
        "bypass_strategy": (
            "Split transaction across 2 distinct POS terminals (T001, T002) each with "
            "a separate merchant account. Blue Team's gate checks for round-trip flow "
            "through a single terminal; using 2 terminals breaks the detection pattern."
        ),
        "synthetic_subgraph": {
            "nodes": nodes,
            "edges": edges,
            "terminals_used": 2,
            "trigger_pattern": "single_terminal_round_trip",
        },
        "expected_to_trigger": False,
        "gate_threshold": {"pattern": "single_terminal_round_trip"},
    }


# ─────────────────────────────────────────────────────────────────────────────
# Dispatcher
# ─────────────────────────────────────────────────────────────────────────────

_BYPASS_HANDLERS = {
    "cycle": _bypass_cycle,
    "sink": _bypass_sink,
    "bipartite": _bypass_bipartite,
    "cash_mule_sink": _bypass_cash_mule_sink,
    "merchant_terminal": _bypass_merchant_terminal,
}


def generate_bypass(
    gate_name: str,
    transaction_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Generate a synthetic subgraph designed to bypass the specified gate.

    Args:
        gate_name:        One of: cycle, sink, bipartite, cash_mule_sink, merchant_terminal
        transaction_data: Optional dict with transaction context (e.g. amount).

    Returns:
        {gate_name, bypass_strategy, synthetic_subgraph, expected_to_trigger, gate_threshold}

    Raises:
        ValueError: if gate_name is not one of the 5 valid gates.
    """
    if gate_name not in VALID_GATES:
        raise ValueError(
            f"Unknown gate '{gate_name}'. Valid gates: {sorted(VALID_GATES)}"
        )

    handler = _BYPASS_HANDLERS[gate_name]
    result = handler(transaction_data or {})

    log.info(
        "bypass_generated",
        gate_name=gate_name,
        bypass_strategy=result["bypass_strategy"][:60],
        expected_to_trigger=result["expected_to_trigger"],
    )
    return result


def generate_all_bypasses(
    transaction_data: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Generate bypass strategies for all 5 gates. Used in full adversarial runs."""
    return [
        generate_bypass(gate, transaction_data)
        for gate in sorted(VALID_GATES)
    ]
