from __future__ import annotations

import pytest

from app.engines.mutation_engine import generate_mutations
from app.engines.seed_library import get_seed


def test_sparse_payload_with_missing_night_ratio_still_gets_context_senior_mutation():
    """
    Send a payload missing night_txn_ratio entirely, confirm context_senior 
    mutation is still produced and injected_features includes night_txn_ratio.
    """
    # Create a minimal sparse vector that does NOT contain night_txn_ratio
    # (or any context feature being manipulated).
    sparse_vector = {
        "txn_amount": 10000.0,
        "amount_zscore": 1.0,
    }
    
    mutations = generate_mutations(sparse_vector, "structuring", n=22)
    
    # Verify we still generated the mutation that targets night_txn_ratio
    senior_mutation = next((m for m in mutations if m["mutation_type"] == "context_senior"), None)
    assert senior_mutation is not None, "context_senior mutation was dropped!"
    
    assert "night_txn_ratio" in senior_mutation.get("injected_features", [])
    assert "night_txn_ratio" in senior_mutation.get("delta_features", {})


def test_full_payload_produces_all_22_mutations():
    """
    Confirm BAF seed vectors (which have all 59 features) still produce exactly 22 mutations,
    unaffected by this change.
    """
    baf_seed = get_seed("digital_arrest")
    
    # Generate mutations
    mutations = generate_mutations(baf_seed, "digital_arrest", n=22)
    
    # Ensure exactly 22 mutations were produced
    assert len(mutations) == 22, f"Expected 22 mutations from full seed, got {len(mutations)}"


def test_sparse_payload_produces_22_mutations_with_injections():
    """
    Send a payload with only 20 features, confirm it now also produces 22 
    mutations (previously would have produced fewer).
    """
    baf_seed = get_seed("digital_arrest")
    
    # Slice the first 20 keys to make it extremely sparse
    sparse_keys = list(baf_seed.keys())[:20]
    sparse_vector = {k: baf_seed[k] for k in sparse_keys}
    
    mutations = generate_mutations(sparse_vector, "digital_arrest", n=22)
    
    # Ensure exactly 22 mutations were produced even though the vector is sparse
    assert len(mutations) == 22, f"Expected 22 mutations from sparse seed, got {len(mutations)}"
