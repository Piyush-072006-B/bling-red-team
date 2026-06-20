"""
Self-Generator — Autonomous Adversarial Pattern Generation
============================================================
When no Blue Team signals arrive, Red Team generates its own
adversarial patterns from the seed library on a schedule.
"""

from __future__ import annotations

import asyncio
import random
import uuid
from datetime import datetime, timezone
from typing import Any

from app.config import get_settings
from app.engines.seed_library import get_all_seeds, get_seed_with_variation
from app.utils.audit_logger import get_logger

log = get_logger(__name__)


async def run_self_generation_cycle(n_archetypes: int = 3) -> list[str]:
    """Pick n random archetypes, generate synthetic FraudDNA payloads, push to ingest queue.

    Returns list of ingest_ids created.
    """
    from app.ingest.router import _queues, ingest_signal
    from app.ingest.schemas import FraudDNA

    all_archetypes = list(get_all_seeds().keys())
    chosen = random.sample(all_archetypes, min(n_archetypes, len(all_archetypes)))
    ingest_ids: list[str] = []

    for archetype in chosen:
        seed = get_seed_with_variation(archetype, variation_pct=0.15)

        # Top 5 features by absolute value for shap_values
        sorted_feats = sorted(
            ((k, v) for k, v in seed.items() if isinstance(v, (int, float))),
            key=lambda x: abs(x[1]),
            reverse=True,
        )[:5]

        payload = FraudDNA(
            source_type="FRAUD_DNA",
            transaction_id=f"SELF_GEN_{archetype}_{uuid.uuid4().hex[:8]}",
            account_id=f"SEED_ACC_{archetype}",
            confirmed_archetype=archetype,
            feature_vector=seed,
            shap_values=dict(sorted_feats),
            timestamp=datetime.now(timezone.utc),
        )

        try:
            result = await ingest_signal(payload)
            ingest_ids.append(result["ingest_id"])
            log.info(
                "self_gen_queued",
                archetype=archetype,
                ingest_id=result["ingest_id"],
                priority=result["priority"],
            )
        except Exception as exc:
            # DuplicateIngestError or QueueFullError — log and skip
            log.warning("self_gen_skip", archetype=archetype, error=str(exc))

    log.info("self_gen_cycle_complete", archetypes=chosen, count=len(ingest_ids))
    return ingest_ids


async def start_self_generation_loop(
    interval_seconds: int = 300,
    enabled: bool = True,
) -> None:
    """Run run_self_generation_cycle() every interval_seconds.

    Backpressure: pauses if total queue depth > 50.
    Stops cleanly on asyncio.CancelledError.
    """
    if not enabled:
        log.info("self_generation_disabled")
        return

    settings = get_settings()
    n = settings.self_generation_archetypes_per_cycle
    log.info("self_generation_loop_started", interval=interval_seconds, n_archetypes=n)

    while True:
        try:
            # Backpressure — check total queue depth
            from app.ingest.router import _queues
            total_pending = sum(q.qsize() for q in _queues.values())
            if total_pending > 50:
                log.info("self_gen_backpressure", pending=total_pending)
            else:
                await run_self_generation_cycle(n_archetypes=n)
        except asyncio.CancelledError:
            log.info("self_generation_loop_cancelled")
            break
        except Exception as exc:
            log.error("self_gen_loop_error", error=str(exc))

        try:
            await asyncio.sleep(interval_seconds)
        except asyncio.CancelledError:
            log.info("self_generation_loop_cancelled")
            break
