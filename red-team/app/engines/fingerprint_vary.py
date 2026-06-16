"""
Isolation Forest Evasion
========================
Varies structural fingerprint features randomly so IF never sees 
identical fingerprints across multiple mutations of the same archetype.
"""

from __future__ import annotations

import random
from typing import Any

IF_STRUCTURAL_FEATURES = [
    "pagerank_fraud_seeded",
    "betweenness_centrality",
    "clustering_coefficient",
    "degree_centrality",
    "community_fraud_ratio",
    "shortest_path_to_fraud",
    "cycle_membership",
    "sink_score",
    "bipartite_score",
    "fan_out_ratio",
    "temporal_acceleration",
    "cash_mule_sink_score",
    "bridge_node_probability",
    "dormancy_reactivation_flag",
    "account_age_days",
    "kyc_completeness_score",
    "distinct_counterparties_30d",
]

def vary_structural_fingerprint(feature_vector: dict[str, float]) -> dict[str, float]:
    """Slightly randomise the 17 IF structural features by ±0.03-0.07."""
    # We edit in-place or return dict. Returning same dict modified for efficiency since we own it.
    for feature in IF_STRUCTURAL_FEATURES:
        if feature in feature_vector:
            val = feature_vector[feature]
            # determine random offset between 0.03 and 0.07, randomly positive or negative
            offset = random.uniform(0.03, 0.07)
            if random.choice([True, False]):
                offset = -offset
            
            new_val = val + offset
            
            # Keep probabilities / ratios in [0, 1] range if appropriate.
            # E.g. shortest_path_to_fraud, account_age_days, distinct_counterparties_30d are not 0-1
            # But the instructions say "±0.03-0.07 randomly". 
            # We'll just apply it generically.
            if feature not in ["shortest_path_to_fraud", "account_age_days", "distinct_counterparties_30d"]:
                new_val = max(0.0, min(1.0, new_val))
            else:
                new_val = max(0.0, new_val) # must be positive
                
            feature_vector[feature] = new_val
    return feature_vector
