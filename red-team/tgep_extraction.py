import asyncio
import sys
import os
import json
sys.path.insert(0, os.path.abspath('d:/bling-red-team/red-team'))

from app.worker.pipeline import _pipeline_fraud_dna
from app.ingest.schemas import FraudDNA
from app.engines.seed_library import get_seed
from app.knowledge.kb_store import _evasion_kb

async def main():
    seed = get_seed("digital_arrest")
    payload = FraudDNA(
        source_type="FRAUD_DNA",
        transaction_id="TEST-DA-002",
        account_id="ACC-TEST-002",
        confirmed_archetype="digital_arrest",
        feature_vector=seed,
        shap_values={"amount_zscore": 0.5},
        timestamp="2026-06-23T10:00:00Z"
    )

    print("Running pipeline manually...")
    await _pipeline_fraud_dna("TEST-DA-002", payload)

    print("Pipeline complete. Extracting from evasion_kb...")
    
    # Filter for graph_bypass_
    graph_bypass = [e for e in _evasion_kb if e["mutation_type"].startswith("graph_bypass_")]
    
    print(f"Found {len(graph_bypass)} graph_bypass_ evasions.")
    
    for bypass in graph_bypass:
        print("========================================")
        print(f"MUTATION TYPE: {bypass['mutation_type']}")
        print("========================================")
        print(json.dumps(bypass.get("tgep_graph", []), indent=2))
        print("\n")

if __name__ == "__main__":
    asyncio.run(main())
