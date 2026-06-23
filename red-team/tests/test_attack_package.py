"""
Tests for attack_package.py and graph_exporter.py outputs.
"""
import json
import os
import pytest

from app.outputs.graph_exporter import evasion_to_tgep_graph, get_graph_for_mutation
from app.outputs.attack_package import build_attack_package, package_to_json_file


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

SAMPLE_EVASION = {
    "archetype": "digital_arrest",
    "evasion_vector": {"avg_txn_amount_30d": 80000.0},
    "feature_deltas": {"night_txn_ratio": -0.35},
    "mutation_type": "timing_day",
    "gate_probe_result": None,
    "feature_sensitivity_result": None,
    "context_bypass_result": None,
    "tgep_threat_level": None,
    "tgep_response": None,
}


# ─────────────────────────────────────────────────────────────────────────────
# Graph exporter tests
# ─────────────────────────────────────────────────────────────────────────────


def test_evasion_to_tgep_graph_digital_arrest_has_4_hops():
    """digital_arrest graph must have exactly 4 chain edges (+ 2 decoys = 6 total)."""
    edges = evasion_to_tgep_graph(SAMPLE_EVASION, "digital_arrest")
    # 4 chain hops + 2 sub-threshold decoy transfers
    assert len(edges) == 6


def test_evasion_to_tgep_graph_structuring_has_7_receivers():
    """structuring graph must have 7 distinct receivers."""
    evasion = {"evasion_vector": {"avg_txn_amount_30d": 45000.0}}
    edges = evasion_to_tgep_graph(evasion, "structuring")
    assert len(edges) == 7
    to_accounts = {e["to_account"] for e in edges}
    assert len(to_accounts) > 0


def test_evasion_to_tgep_graph_all_edges_have_required_fields():
    """Every edge must have from_account, to_account, amount, payment_rail, timestamp."""
    required = {"from_account", "to_account", "amount", "payment_rail", "timestamp"}
    for archetype in [
        "digital_arrest", "structuring", "cycle_round_trip", "rapid_layering",
        "bipartite_mule", "account_takeover", "otp_fraud", "sim_swap",
        "pig_butchering", "romance_scam", "salary_mule", "low_slow_mule",
        "investment_fraud", "ghost_node_cash", "merchant_terminal", "NEW_VARIANT",
    ]:
        edges = evasion_to_tgep_graph({"evasion_vector": {}}, archetype)
        assert len(edges) > 0, f"{archetype} produced no edges"
        for edge in edges:
            missing = required - set(edge.keys())
            assert not missing, f"{archetype}: edge missing fields {missing}"


def test_graph_bypass_type_uses_prebuilt_graph():
    """get_graph_for_mutation for graph_bypass_nine_hop_linear should return 6 edges."""
    edges = get_graph_for_mutation(
        mutation_type="graph_bypass_nine_hop_linear",
        evasion_vector={},
        archetype="structuring",
    )
    assert len(edges) == 6


# ─────────────────────────────────────────────────────────────────────────────
# Attack package tests
# ─────────────────────────────────────────────────────────────────────────────


def test_build_attack_package_has_tgep_graph():
    """build_attack_package must include tgep_graph, bypass_strategy, attack_id."""
    pkg = build_attack_package(SAMPLE_EVASION, "digital_arrest")
    assert "tgep_graph" in pkg
    assert len(pkg["tgep_graph"]) > 0
    assert "attack_id" in pkg
    assert "bypass_strategy" in pkg
    assert "mutation_type" in pkg
    assert "feature_deltas" in pkg
    assert "created_at" in pkg


def test_package_to_json_file_creates_file(tmp_path, monkeypatch):
    """package_to_json_file must create a readable JSON file at the expected path."""
    # Monkeypatch OUTPUT_DIR to use tmp_path
    import app.outputs.attack_package as ap_module
    original_dir = ap_module._OUTPUT_DIR
    ap_module._OUTPUT_DIR = tmp_path

    try:
        pkg = build_attack_package(SAMPLE_EVASION, "digital_arrest")
        file_path = package_to_json_file(pkg)

        assert os.path.isfile(file_path), f"File not found: {file_path}"

        with open(file_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)

        assert isinstance(data, list)
        assert len(data) > 0
    finally:
        ap_module._OUTPUT_DIR = original_dir
