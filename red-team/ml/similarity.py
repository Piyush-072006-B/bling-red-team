"""
ML Similarity — Cosine Similarity for Archetype Matching
==========================================================
Provides cosine similarity between feature vectors represented as dicts.
Uses scikit-learn's cosine_similarity under the hood (sklearn only, no heavy deps).
"""

from __future__ import annotations

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity


def cosine_sim(vec_a: dict[str, float], vec_b: dict[str, float]) -> float:
    """
    Compute cosine similarity between two feature vectors represented as dicts.

    Handles sparse vectors: only the union of keys from both dicts is used.
    Missing keys are treated as 0.

    Args:
        vec_a: First feature vector {feature_name: value}
        vec_b: Second feature vector {feature_name: value}

    Returns:
        Cosine similarity in range [-1.0, 1.0]. Returns 0.0 if either is all-zero.
    """
    all_keys = sorted(set(vec_a) | set(vec_b))
    if not all_keys:
        return 0.0

    a = np.array([[vec_a.get(k, 0.0) for k in all_keys]], dtype=float)
    b = np.array([[vec_b.get(k, 0.0) for k in all_keys]], dtype=float)

    # Guard against zero vectors (cosine_similarity returns NaN for zero vectors)
    if np.linalg.norm(a) == 0.0 or np.linalg.norm(b) == 0.0:
        return 0.0

    result = cosine_similarity(a, b)
    return float(result[0][0])


def normalise_vector(vec: dict[str, float]) -> dict[str, float]:
    """
    L2-normalise a feature vector dict.

    Returns a new dict with the same keys, values scaled so that
    the Euclidean norm of the value array equals 1.0.
    If the vector is all-zero, returns it unchanged.
    """
    if not vec:
        return vec

    keys = list(vec.keys())
    values = np.array([vec[k] for k in keys], dtype=float)
    norm = np.linalg.norm(values)

    if norm == 0.0:
        return vec

    normed = (values / norm).tolist()
    return dict(zip(keys, normed))
