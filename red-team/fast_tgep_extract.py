import sys
import os
import json
sys.path.insert(0, os.path.abspath('d:/bling-red-team/red-team'))

from app.engines.tgep_bypass_graphs import generate_tgep_bypass_graph
from app.engines.seed_library import get_seed

def main():
    seed = get_seed("digital_arrest")
    
    target_types = [
        "sink_with_outflow", 
        "slow_bipartite", 
        "nine_hop_linear", 
        "mule_warmup_graph"
    ]
    
    for t in target_types:
        graph = generate_tgep_bypass_graph("digital_arrest", t)
        print("========================================")
        print(f"MUTATION TYPE: graph_bypass_{t}")
        print("========================================")
        print(json.dumps(graph, indent=2))
        print("\n")

if __name__ == "__main__":
    main()
