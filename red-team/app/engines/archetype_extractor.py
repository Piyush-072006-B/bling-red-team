"""
Archetype Extractor — Map 59-Feature Vector → 16 Archetypes or NEW_VARIANT
============================================================================
Uses cosine similarity between the incoming feature_vector (normalised)
and each archetype signature centroid from ARCHETYPE_SIGNATURES.

If max similarity < NEW_VARIANT_THRESHOLD (0.45), labels as NEW_VARIANT.

Returns: {"archetype": str, "similarity": float, "all_scores": dict[str, float]}
"""

from __future__ import annotations

from ml.similarity import cosine_sim, normalise_vector
from app.utils.audit_logger import get_logger

log = get_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Archetype signature centroids
# Each archetype is defined by its dominant feature names with weight 1.0.
# Incoming vectors are normalised before comparison.
# ─────────────────────────────────────────────────────────────────────────────

from app.engines.seed_library import get_all_seeds

ARCHETYPE_SIGNATURES = get_all_seeds()

# Precompute normalised signature centroids once at module load
_NORMALISED_SIGNATURES: dict[str, dict[str, float]] = {
    archetype: normalise_vector(sig)
    for archetype, sig in ARCHETYPE_SIGNATURES.items()
}

NEW_VARIANT_THRESHOLD = 0.45


def extract_archetype(feature_vector: dict[str, float]) -> dict[str, object]:
    """
    Map a feature vector to the best-matching archetype via cosine similarity.

    Args:
        feature_vector: Dict of {feature_name: float} — the 59-feature fraud signal.

    Returns:
        {
            "archetype":   str,          # best match or "NEW_VARIANT"
            "similarity":  float,        # similarity to best match (0–1)
            "all_scores":  dict[str, float],  # similarity to every archetype
            "is_novel":    bool,         # True when similarity < 0.45
        }
    """
    if not feature_vector:
        log.warning("extract_archetype_empty_vector")
        return {
            "archetype": "NEW_VARIANT",
            "similarity": 0.0,
            "all_scores": {},
            "is_novel": True,
        }

    normed_input = normalise_vector(feature_vector)

    all_scores: dict[str, float] = {}
    for archetype, centroid in _NORMALISED_SIGNATURES.items():
        score = cosine_sim(normed_input, centroid)
        all_scores[archetype] = round(score, 6)

    best_archetype = max(all_scores, key=lambda k: all_scores[k])
    best_score = all_scores[best_archetype]

    is_novel = best_score < NEW_VARIANT_THRESHOLD
    final_archetype = "NEW_VARIANT" if is_novel else best_archetype

    log.info(
        "archetype_extracted",
        archetype=final_archetype,
        similarity=round(best_score, 4),
        is_novel=is_novel,
    )

    return {
        "archetype": final_archetype,
        "similarity": best_score,
        "all_scores": all_scores,
        "is_novel": is_novel,
    }
