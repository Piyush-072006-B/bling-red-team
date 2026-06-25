"""
Export All TGEP Graphs — Generate TGEP edge arrays for all 16 remaining archetypes.
====================================================================================
Calls evasion_to_tgep_graph() for each archetype and saves the result to
data/all_tgep_graphs.json. Also prints each graph to terminal for manual
copy-paste into TGEP.

Usage:
    python scripts/export_all_tgep_graphs.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

# All archetypes to export (digital_arrest confirmed already — still included for completeness)
ARCHETYPES = [
    "digital_arrest",
    "structuring",
    "rapid_layering",
    "bipartite_mule",
    "cycle_round_trip",
    "cash_in_mule",
    "salary_mule",
    "low_slow_mule",
    "romance_scam",
    "pig_butchering",
    "investment_fraud",
    "account_takeover",
    "otp_fraud",
    "sim_swap",
    "ghost_node_cash",
    "merchant_terminal",
    "NEW_VARIANT",
]


def export_all() -> dict:
    from app.outputs.graph_exporter import evasion_to_tgep_graph

    all_graphs: dict = {}

    for archetype in ARCHETYPES:
        edges = evasion_to_tgep_graph({"evasion_vector": {}}, archetype)
        all_graphs[archetype] = edges

        # Print to terminal for manual TGEP testing
        print(f"\n{'='*70}")
        print(f"  ARCHETYPE: {archetype}")
        print(f"  EDGES: {len(edges)} | ACCOUNTS: {len({a for e in edges for a in (e['from_account'], e['to_account'])})}")
        print(f"{'='*70}")
        print(json.dumps(edges, indent=2))

    return all_graphs


def main() -> None:
    all_graphs = export_all()

    output_path = _ROOT / "data" / "all_tgep_graphs.json"
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(all_graphs, fh, indent=2)

    print(f"\n[export_all_tgep_graphs] Saved {len(all_graphs)} graphs to {output_path}")
    print("[export_all_tgep_graphs] Paste each graph array into TGEP /transaction/manual endpoint.")


if __name__ == "__main__":
    main()
