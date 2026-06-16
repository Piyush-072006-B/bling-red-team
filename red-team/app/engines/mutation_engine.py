"""
Mutation Engine — Perturb Features to Evade Blue Team Score
=============================================================
For a given feature_vector and confirmed_archetype, generates N=10 mutations
designed to reduce the Blue Team fraud score below detection thresholds.

Mutation types (5 families, producing ≥10 variants):
  1. threshold_amount   — shift amount to 0.92× below threshold (structuring evasion)
  2. timing_day         — push night_txn_ratio to 0.15, hour_deviation to 0
  3. velocity_20pct     — reduce burst_score / velocity_ratio by 20%
  4. velocity_40pct     — reduce burst_score / velocity_ratio by 40%
  5. context_festival   — flip is_festival_period=1 (0.70 multiplier in Blue Team)
  6. context_senior     — remove night flag for senior accounts (age > 60)
  7. novelty_zero       — set counterparty_novelty=0 (pretend payee is known)
  8. threshold_100k     — shift to 0.92× below 100000 threshold
  9. threshold_1m       — shift to 0.92× below 1000000 threshold
  10. velocity_30pct    — reduce burst_score / velocity_ratio by 30%

Each mutation returns:
    {
        mutation_id:     str (uuid4),
        mutation_type:   str,
        delta_features:  dict[str, float],   # only changed features
        original_vector: dict[str, float],
        mutated_vector:  dict[str, float],
    }
"""

from __future__ import annotations

import copy
import uuid
from typing import Any

from app.utils.audit_logger import get_logger

log = get_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Structuring thresholds (Indian AML — ₹ amounts normalised to 0-1 range)
# Raw amounts: 50000, 100000, 1000000
# In the feature vector, amount_series_score / amount_vs_threshold_* are typically
# 0–1 scores produced by Blue Team's feature engineering.  We treat them as direct
# 0–1 features and clamp mutations to [0, 1].
# ─────────────────────────────────────────────────────────────────────────────

_THRESHOLD_EVASION_FACTOR = 0.92  # bring score just below threshold

# Amount feature keys and their "above-threshold" sentinel (score = 1.0 means at/above threshold)
_THRESHOLD_FEATURES_50K = [
    "amount_vs_threshold_50000",
    "amount_series_score",
]
_THRESHOLD_FEATURES_100K = [
    "amount_vs_threshold_100000",
]
_THRESHOLD_FEATURES_1M = [
    "amount_vs_threshold_1000000",
]

# Velocity features
_VELOCITY_FEATURES = ["burst_score", "velocity_ratio"]

# Timing features
_TIMING_FEATURES = {
    "night_txn_ratio": 0.15,
    "hour_deviation": 0.0,
}

# Context features
_FESTIVAL_FEATURE = "is_festival_period"
_SENIOR_NIGHT_FEATURE = "night_txn_ratio"

# Novelty feature
_NOVELTY_FEATURE = "counterparty_novelty"


# ─────────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────────


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _apply_delta(
    base: dict[str, float],
    overrides: dict[str, float],
) -> tuple[dict[str, float], dict[str, float]]:
    """
    Return (mutated_vector, delta_features).
    Only keys in overrides are changed; rest is copied unchanged.
    """
    mutated = copy.deepcopy(base)
    delta: dict[str, float] = {}
    for k, new_val in overrides.items():
        old_val = base.get(k, 0.0)
        clamped = new_val if new_val > 1.0 else _clamp(new_val)
        mutated[k] = clamped
        if abs(clamped - old_val) > 1e-9:
            delta[k] = round(clamped - old_val, 6)
    return mutated, delta


def build_mutation(
    mutation_type: str,
    original: dict[str, float],
    overrides: dict[str, float],
) -> dict[str, Any] | None:
    """Build a mutation record, or return None if no features actually changed."""
    mutated, delta = _apply_delta(original, overrides)
    if not delta:
        return None  # nothing changed — skip this mutation
    return {
        "mutation_id": str(uuid.uuid4()),
        "mutation_type": mutation_type,
        "delta_features": delta,
        "original_vector": copy.deepcopy(original),
        "mutated_vector": mutated,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Individual mutation strategies
# ─────────────────────────────────────────────────────────────────────────────


def _threshold_mutation(
    original: dict[str, float],
    features: list[str],
    label: str,
) -> dict[str, Any] | None:
    """Reduce threshold-sensitive features by EVASION_FACTOR."""
    overrides = {
        k: original.get(k, 1.0) * _THRESHOLD_EVASION_FACTOR
        for k in features
        if k in original or original.get(k, 0) > 0
    }
    if not overrides:
        # Feature not present — set to a low value
        overrides = {k: 0.85 * _THRESHOLD_EVASION_FACTOR for k in features}
    return build_mutation(label, original, overrides)


def _velocity_mutation(
    original: dict[str, float],
    reduction_pct: float,
    label: str,
) -> dict[str, Any] | None:
    """Reduce velocity features by reduction_pct percent."""
    factor = 1.0 - reduction_pct
    overrides = {
        k: original.get(k, 1.0) * factor
        for k in _VELOCITY_FEATURES
    }
    return build_mutation(label, original, overrides)


def _timing_mutation(original: dict[str, float]) -> dict[str, Any] | None:
    """Push timing features toward daytime pattern."""
    overrides = {k: v for k, v in _TIMING_FEATURES.items()}
    return build_mutation("timing_day", original, overrides)


def _context_festival_mutation(original: dict[str, float]) -> dict[str, Any] | None:
    """Flip is_festival_period to 1 to exploit 0.70 multiplier in Blue Team."""
    overrides = {_FESTIVAL_FEATURE: 1.0}
    return build_mutation("context_festival", original, overrides)


def _context_senior_mutation(original: dict[str, float]) -> dict[str, Any] | None:
    """Remove night flag — mimics senior-account exemption in Blue Team context logic."""
    overrides = {_SENIOR_NIGHT_FEATURE: 0.0}
    return build_mutation("context_senior", original, overrides)


def _novelty_zero_mutation(original: dict[str, float]) -> dict[str, Any] | None:
    """Set counterparty_novelty=0 — pretend payee is a known counterparty."""
    overrides = {_NOVELTY_FEATURE: 0.0}
    return build_mutation("novelty_zero", original, overrides)


# ─────────────────────────────────────────────────────────────────────────────
# Compound Mutations
# ─────────────────────────────────────────────────────────────────────────────


def _compound_daytime_slowdown(original: dict[str, float]) -> dict[str, Any] | None:
    overrides = {
        "night_txn_ratio": 0.10,
        "hour_deviation": 0.0,
        "burst_score": original.get("burst_score", 1.0) * 0.7,
        "velocity_ratio": original.get("velocity_ratio", 1.0) * 0.7,
        "channel_entropy": 0.3,
    }
    return build_mutation("compound_daytime_slowdown", original, overrides)


def _compound_structuring_ghost(original: dict[str, float]) -> dict[str, Any] | None:
    overrides = {
        "amount_series_score": original.get("amount_series_score", 1.0) * 0.88,
        "amount_vs_threshold_50000": original.get("amount_vs_threshold_50000", 1.0) * 0.88,
        "counterparty_novelty": 0.0,
        "txn_count_30d": 3.0,
    }
    return build_mutation("compound_structuring_ghost", original, overrides)


def _compound_festival_layering(original: dict[str, float]) -> dict[str, Any] | None:
    overrides = {
        "is_festival_period": 1.0,
        "velocity_ratio": original.get("velocity_ratio", 1.0) * 0.75,
        "burst_score": original.get("burst_score", 1.0) * 0.75,
        "night_txn_ratio": 0.1,
    }
    return build_mutation("compound_festival_layering", original, overrides)


def _compound_mule_warmup(original: dict[str, float]) -> dict[str, Any] | None:
    overrides = {
        "dormancy_reactivation_flag": 0.0,
        "txn_count_30d": 12.0,
        "avg_txn_amount_30d": 15000.0,
        "burst_score": original.get("burst_score", 1.0) * 0.6,
    }
    return build_mutation("compound_mule_warmup", original, overrides)


def _compound_kyc_ghost(original: dict[str, float]) -> dict[str, Any] | None:
    overrides = {
        "kyc_completeness_score": 0.9,
        "counterparty_novelty": 0.0,
        "geography_switch": 0.0,
        "channel_switch": 0.0,
    }
    return build_mutation("compound_kyc_ghost", original, overrides)


def _compound_senior_festival_night(original: dict[str, float]) -> dict[str, Any] | None:
    overrides = {
        "night_txn_ratio": 0.0,
        "is_festival_period": 1.0,
        "payee_vpa_age_days": 30.0,
        "amount_zscore": 1.5,
    }
    return build_mutation("compound_senior_festival_night", original, overrides)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────


def generate_mutations(
    feature_vector: dict[str, float],
    archetype: str,
    n: int = 22,
) -> list[dict[str, Any]]:
    """
    Generate up to N mutations of a feature vector designed to evade Blue Team scoring.

    Args:
        feature_vector: The original 59-feature vector.
        archetype:      Confirmed archetype label (used for targeted mutation selection).
        n:              Number of mutations to return (default 22).

    Returns:
        List of up to N mutation dicts, each containing:
            mutation_id, mutation_type, delta_features, original_vector, mutated_vector
    """
    from app.engines.tier_aware_mutations import generate_tier_aware_mutations
    from app.engines.fingerprint_vary import vary_structural_fingerprint

    candidates: list[dict[str, Any] | None] = [
        # 1. Threshold — 50k
        _threshold_mutation(feature_vector, _THRESHOLD_FEATURES_50K, "threshold_amount_50k"),
        # 2. Timing
        _timing_mutation(feature_vector),
        # 3. Velocity 20%
        _velocity_mutation(feature_vector, 0.20, "velocity_20pct"),
        # 4. Velocity 40%
        _velocity_mutation(feature_vector, 0.40, "velocity_40pct"),
        # 5. Context festival
        _context_festival_mutation(feature_vector),
        # 6. Context senior night removal
        _context_senior_mutation(feature_vector),
        # 7. Novelty zero
        _novelty_zero_mutation(feature_vector),
        # 8. Threshold — 100k
        _threshold_mutation(feature_vector, _THRESHOLD_FEATURES_100K, "threshold_amount_100k"),
        # 9. Threshold — 1M
        _threshold_mutation(feature_vector, _THRESHOLD_FEATURES_1M, "threshold_amount_1m"),
        # 10. Velocity 30%
        _velocity_mutation(feature_vector, 0.30, "velocity_30pct"),
        # 11. Compound Daytime Slowdown
        _compound_daytime_slowdown(feature_vector),
        # 12. Compound Structuring Ghost
        _compound_structuring_ghost(feature_vector),
        # 13. Compound Festival Layering
        _compound_festival_layering(feature_vector),
        # 14. Compound Mule Warmup
        _compound_mule_warmup(feature_vector),
        # 15. Compound KYC Ghost
        _compound_kyc_ghost(feature_vector),
        # 16. Compound Senior Festival Night
        _compound_senior_festival_night(feature_vector),
    ]

    # 17-22. Tier-aware compound mutations
    candidates.extend(generate_tier_aware_mutations(feature_vector))

    mutations = [m for m in candidates if m is not None]

    # If an archetype has a specialised first-priority mutation, move it to front
    _prioritise_for_archetype(mutations, archetype)

    result = mutations[:n]

    # Apply Isolation Forest fingerprint variance to every mutation
    for m in result:
        vary_structural_fingerprint(m["mutated_vector"])

    log.info(
        "mutations_generated",
        archetype=archetype,
        requested=n,
        produced=len(result),
    )
    return result


def _prioritise_for_archetype(
    mutations: list[dict[str, Any]],
    archetype: str,
) -> None:
    """
    In-place reorder: move the most relevant mutation type to index 0
    based on the confirmed archetype.
    """
    priority_map: dict[str, str] = {
        "structuring": "threshold_amount_50k",
        "digital_arrest": "timing_day",
        "otp_fraud": "velocity_20pct",
        "pig_butchering": "velocity_20pct",
        "romance_scam": "novelty_zero",
        "account_takeover": "velocity_20pct",
        "low_slow_mule": "velocity_20pct",
        "sim_swap": "velocity_20pct",
    }
    preferred_type = priority_map.get(archetype)
    if not preferred_type:
        return

    for i, m in enumerate(mutations):
        if m.get("mutation_type") == preferred_type and i != 0:
            mutations.insert(0, mutations.pop(i))
            break
