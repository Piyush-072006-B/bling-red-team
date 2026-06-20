"""
Seed Library — Baseline Feature Vectors for Adversarial Pattern Generation
==========================================================================
Provides realistic 59-feature vectors for all 16 archetypes derived from
BAF NeurIPS 2022 + PaySim fraud dataset statistics. Used when no Blue Team
signal is available so Red Team can self-generate adversarial patterns.
"""

from __future__ import annotations

import copy
import random
from typing import Any

from app.engines.seed_data import ARCHETYPE_SEEDS


def get_seed(archetype: str) -> dict[str, float]:
    """Return the seed vector for the given archetype (deep copy).

    Falls back to 'structuring' if archetype is not in the library.
    """
    return copy.deepcopy(
        ARCHETYPE_SEEDS.get(archetype, ARCHETYPE_SEEDS["structuring"])
    )


def get_all_seeds() -> dict[str, dict[str, float]]:
    """Return the full ARCHETYPE_SEEDS dict (deep copy)."""
    return copy.deepcopy(ARCHETYPE_SEEDS)


def get_seed_with_variation(
    archetype: str,
    variation_pct: float = 0.1,
) -> dict[str, float]:
    """Return seed with ±variation_pct random noise on all numeric values.

    Binary flags (0/1) and community_id are left untouched.
    """
    seed = get_seed(archetype)
    # Fields that should not be perturbed (binary flags or identifiers)
    skip_fields = {
        "channel_upi", "channel_imps", "channel_rtgs", "channel_neft",
        "is_weekend", "is_night", "is_festival_period",
        "dormancy_reactivation_flag", "dormancy_break",
        "geography_switch", "channel_switch", "txn_amount_rounded",
        "community_id", "payee_in_alert_log",
    }
    for key, val in seed.items():
        if key in skip_fields:
            continue
        if isinstance(val, (int, float)) and val != 0:
            noise = val * random.uniform(-variation_pct, variation_pct)
            seed[key] = round(val + noise, 6)
    return seed
