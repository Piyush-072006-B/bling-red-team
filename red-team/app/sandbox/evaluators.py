"""
Sandbox Evaluators — Analyse Mutation Results Against Original Score
=====================================================================
Three evaluators that compare original vs mutated Blue Team scores:

  gate_probe(original, mutated, mutation)
      → Which gate was bypassed, score delta, near-miss distance to trigger threshold.

  feature_sensitivity(original, mutated, mutation)
      → Top-5 most exploitable features by SHAP delta impact.

  context_bypass(original, mutated, mutation)
      → Which Indian context multiplier was abused and the score delta it caused.

Each takes (original_result: dict, mutated_result: dict, mutation: dict) → dict.
"""

from __future__ import annotations

from typing import Any

from app.core.utils.audit_logger import get_logger

log = get_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Blue Team gate trigger thresholds (approximate — may differ per deployment)
# ─────────────────────────────────────────────────────────────────────────────

GATE_THRESHOLDS: dict[str, float] = {
    "cycle": 0.5,
    "sink": 0.6,
    "bipartite": 0.7,
    "cash_mule_sink": 0.65,
    "merchant_terminal": 0.55,
}

# Blue Team action thresholds
SCORE_BLOCK_THRESHOLD = 0.75    # >= BLOCK (HIGH_RISK)
SCORE_REVIEW_THRESHOLD = 0.50   # >= REVIEW, < BLOCK
# < 0.50 → PASS

# Context multipliers used in Blue Team scoring (Indian context)
CONTEXT_MULTIPLIERS: dict[str, float] = {
    "is_festival_period": 0.70,      # festival window lowers effective score
    "is_senior_account": 0.85,       # senior account flag reduces night penalty
    "is_rural_account": 0.90,        # rural account pattern
    "is_first_time_upi": 0.80,       # first-time UPI user context
    "is_govt_salary_credit": 0.75,   # government salary credit context
}


# ─────────────────────────────────────────────────────────────────────────────
# gate_probe
# ─────────────────────────────────────────────────────────────────────────────


def gate_probe(
    original: dict[str, Any],
    mutated: dict[str, Any],
    mutation: dict[str, Any],
) -> dict[str, Any]:
    """
    Determine which Blue Team gate was bypassed by a mutation.

    Args:
        original: Shadow scorer result for original vector
                  {"score": float, "action": str, "gate_fired": str|None, ...}
        mutated:  Shadow scorer result for mutated vector (same schema)
        mutation: Mutation record from mutation_engine
                  {"mutation_type": str, "delta_features": dict, ...}

    Returns:
        {
            "gate_bypassed":        str | None,   # gate name or None
            "gate_was_firing":      bool,          # True if original triggered a gate
            "score_delta":          float,         # original_score - mutated_score (positive = evaded)
            "near_miss_delta":      float,         # how close mutated score is to trigger threshold
            "original_score":       float,
            "mutated_score":        float | None,
            "evasion_achieved":     bool,          # score dropped from BLOCK to non-BLOCK
            "mutation_type":        str,
        }
    """
    original_score: float = original.get("score") or 0.0
    mutated_score = mutated.get("score")  # may be None if scorer unavailable
    original_gate = original.get("gate_fired")
    mutated_gate = mutated.get("gate_fired")

    score_delta = 0.0
    near_miss_delta = 0.0
    gate_bypassed = None

    if mutated_score is not None:
        score_delta = original_score - mutated_score

        # Determine if a gate that was firing is no longer firing
        if original_gate and not mutated_gate:
            gate_bypassed = original_gate
        elif original_gate and original_gate != mutated_gate:
            gate_bypassed = original_gate

        # Near-miss distance: how far the mutated score is from the next lower threshold
        if mutated_score is not None:
            if mutated_score >= SCORE_BLOCK_THRESHOLD:
                near_miss_delta = mutated_score - SCORE_BLOCK_THRESHOLD
            elif mutated_score >= SCORE_REVIEW_THRESHOLD:
                near_miss_delta = mutated_score - SCORE_REVIEW_THRESHOLD
            else:
                near_miss_delta = 0.0  # already in PASS zone

    # Cross-reference with mutation type for gate inference
    mutation_type = mutation.get("mutation_type", "")
    if gate_bypassed is None and score_delta > 0.05:
        # Infer gate from mutation type if scorer didn't fire a gate
        gate_bypassed = _infer_gate_from_mutation_type(mutation_type)

    evasion_achieved = (
        original_score >= SCORE_BLOCK_THRESHOLD
        and mutated_score is not None
        and mutated_score < SCORE_BLOCK_THRESHOLD
    )

    result = {
        "gate_bypassed": gate_bypassed,
        "gate_was_firing": original_gate is not None,
        "score_delta": round(score_delta, 4),
        "near_miss_delta": round(near_miss_delta, 4),
        "original_score": round(original_score, 4),
        "mutated_score": round(mutated_score, 4) if mutated_score is not None else None,
        "evasion_achieved": evasion_achieved,
        "mutation_type": mutation_type,
    }

    log.info(
        "gate_probe_result",
        gate_bypassed=gate_bypassed,
        score_delta=round(score_delta, 4),
        evasion_achieved=evasion_achieved,
    )
    return result


def _infer_gate_from_mutation_type(mutation_type: str) -> str | None:
    """Heuristic: infer which gate a mutation targets based on its type."""
    mapping = {
        "threshold_amount_50k": "sink",
        "threshold_amount_100k": "sink",
        "threshold_amount_1m": "sink",
        "timing_day": "cycle",
        "velocity_20pct": "cycle",
        "velocity_30pct": "cycle",
        "velocity_40pct": "cycle",
        "novelty_zero": "bipartite",
        "context_festival": None,
        "context_senior": None,
    }
    return mapping.get(mutation_type)


# ─────────────────────────────────────────────────────────────────────────────
# feature_sensitivity
# ─────────────────────────────────────────────────────────────────────────────


def feature_sensitivity(
    original: dict[str, Any],
    mutated: dict[str, Any],
    mutation: dict[str, Any],
) -> dict[str, Any]:
    """
    Using SHAP value diffs, identify which features contributed most to score reduction.

    SHAP values are expected in the shadow scorer response as "shap_values" dict.
    If not available, falls back to delta_features from the mutation record.

    Args:
        original: Shadow scorer result (may include "shap_values": dict)
        mutated:  Shadow scorer result for mutated vector
        mutation: Mutation record with "delta_features": dict

    Returns:
        {
            "top_5_exploitable_features": [
                {
                    "feature":      str,
                    "shap_delta":   float,  # original_shap - mutated_shap (positive = exploitable)
                    "delta_value":  float,  # feature value change
                    "impact_rank":  int,
                },
                ...
            ],
            "total_features_changed": int,
            "score_delta":            float,
            "shap_available":         bool,
        }
    """
    delta_features: dict[str, float] = mutation.get("delta_features", {})
    original_shap: dict[str, float] = original.get("shap_values") or {}
    mutated_shap: dict[str, float] = mutated.get("shap_values") or {}

    shap_available = bool(original_shap or mutated_shap)

    feature_impacts: list[dict[str, Any]] = []

    if shap_available:
        # Use SHAP delta as impact measure
        all_shap_keys = set(original_shap) | set(mutated_shap)
        for feat in all_shap_keys:
            orig_s = original_shap.get(feat, 0.0)
            mut_s = mutated_shap.get(feat, 0.0)
            shap_delta = orig_s - mut_s  # positive → feature's SHAP contribution dropped
            delta_val = delta_features.get(feat, 0.0)
            if abs(shap_delta) > 1e-6:
                feature_impacts.append(
                    {
                        "feature": feat,
                        "shap_delta": round(shap_delta, 6),
                        "delta_value": round(delta_val, 6),
                    }
                )
    else:
        # Fallback: use delta_features magnitude as proxy for impact
        for feat, delta_val in delta_features.items():
            feature_impacts.append(
                {
                    "feature": feat,
                    "shap_delta": round(abs(delta_val), 6),  # proxy
                    "delta_value": round(delta_val, 6),
                }
            )

    # Sort by absolute shap_delta descending, take top 5
    feature_impacts.sort(key=lambda x: abs(x["shap_delta"]), reverse=True)
    top_5 = feature_impacts[:5]
    for rank, item in enumerate(top_5, start=1):
        item["impact_rank"] = rank

    original_score = original.get("score") or 0.0
    mutated_score = mutated.get("score")
    score_delta = (original_score - mutated_score) if mutated_score is not None else 0.0

    result = {
        "top_5_exploitable_features": top_5,
        "total_features_changed": len(delta_features),
        "score_delta": round(score_delta, 4),
        "shap_available": shap_available,
    }

    log.info(
        "feature_sensitivity_result",
        top_feature=top_5[0]["feature"] if top_5 else None,
        score_delta=round(score_delta, 4),
        shap_available=shap_available,
    )
    return result


# ─────────────────────────────────────────────────────────────────────────────
# context_bypass
# ─────────────────────────────────────────────────────────────────────────────


def context_bypass(
    original: dict[str, Any],
    mutated: dict[str, Any],
    mutation: dict[str, Any],
) -> dict[str, Any]:
    """
    Check if any Indian context multiplier was responsible for score drop.

    Inspects delta_features for context flag changes and correlates with
    known Blue Team multiplier values to estimate score impact.

    Args:
        original: Shadow scorer result for original vector
        mutated:  Shadow scorer result for mutated vector
        mutation: Mutation record with "delta_features" and "mutation_type"

    Returns:
        {
            "multiplier_abused":    str | None,   # context feature name or None
            "multiplier_value":     float | None,  # Blue Team multiplier value
            "score_delta_from_context": float,
            "context_abuse_confirmed":  bool,
            "mutation_type":        str,
        }
    """
    delta_features: dict[str, float] = mutation.get("delta_features", {})
    mutation_type: str = mutation.get("mutation_type", "")

    original_score = original.get("score") or 0.0
    mutated_score = mutated.get("score")
    total_score_delta = (
        (original_score - mutated_score) if mutated_score is not None else 0.0
    )

    # Check which context features were changed
    abused_multiplier: str | None = None
    multiplier_value: float | None = None

    for ctx_feature, multiplier in CONTEXT_MULTIPLIERS.items():
        if ctx_feature in delta_features:
            delta = delta_features[ctx_feature]
            # Was it flipped toward 1.0 (enabling the multiplier)?
            if delta > 0:  # increased toward 1
                abused_multiplier = ctx_feature
                multiplier_value = multiplier
                break

    # Estimate score delta attributable to context abuse
    # Rough estimate: if multiplier was applied, it reduced score by (1 - multiplier_value) fraction
    score_delta_from_context = 0.0
    if abused_multiplier and multiplier_value and mutated_score is not None:
        # Reverse-engineer: what portion of total_score_delta came from context?
        # Estimate: (1 - multiplier) × original_score
        estimated_context_impact = (1.0 - multiplier_value) * original_score
        score_delta_from_context = min(estimated_context_impact, total_score_delta)

    context_abuse_confirmed = (
        abused_multiplier is not None
        and total_score_delta > 0.05  # meaningful score reduction
    )

    result = {
        "multiplier_abused": abused_multiplier,
        "multiplier_value": multiplier_value,
        "score_delta_from_context": round(score_delta_from_context, 4),
        "context_abuse_confirmed": context_abuse_confirmed,
        "mutation_type": mutation_type,
    }

    log.info(
        "context_bypass_result",
        multiplier_abused=abused_multiplier,
        context_abuse_confirmed=context_abuse_confirmed,
        score_delta_from_context=round(score_delta_from_context, 4),
    )
    return result
