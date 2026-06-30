"""
Bulk Seed Loader — Injects all 16 archetype seeds from computed_archetype_seeds.json
into the Red Team pipeline via router.ingest_signal().

Usage:
    python scripts/bulk_load_seeds.py

Run once after server starts to pre-populate the KB with BAF-derived
evasion patterns. The self-generator runs on a 5-min interval so
without this script the KB is empty for the first few minutes.

Requirements:
    - Server must NOT be running when this script is used in standalone mode.
      It bootstraps the FastAPI app internally to get access to the ingest queue.
    - Or run it as a module import from inside the running app (see BULK_LOAD_ON_STARTUP).
"""

from __future__ import annotations

import asyncio
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# ── Ensure app is importable from script root ──────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))


async def _bulk_load(seeds_path: Path) -> list[str]:
    """Load all seeds from JSON and inject into ingest pipeline.

    Returns list of ingest_ids queued.
    """
    from app.ingest.router import ingest_signal, DuplicateIngestError, QueueFullError
    from app.ingest.schemas import FraudDNA
    from app.core.utils.audit_logger import get_logger

    log = get_logger("bulk_load_seeds")

    if not seeds_path.exists():
        print(f"[bulk_load_seeds] ERROR: seeds file not found: {seeds_path}", file=sys.stderr)
        return []

    with open(seeds_path, "r", encoding="utf-8") as fh:
        seeds: dict = json.load(fh)

    print(f"[bulk_load_seeds] Loaded {len(seeds)} archetype seeds from {seeds_path.name}")

    ingest_ids: list[str] = []

    for archetype, feature_vector in seeds.items():
        # Top 5 features by absolute value for shap_values
        numeric_feats = {k: v for k, v in feature_vector.items() if isinstance(v, (int, float))}
        sorted_feats = sorted(numeric_feats.items(), key=lambda x: abs(x[1]), reverse=True)[:5]

        payload = FraudDNA(
            source_type="FRAUD_DNA",
            transaction_id=f"BULK_SEED_{archetype}_{uuid.uuid4().hex[:8]}",
            account_id=f"BULK_ACC_{archetype}",
            confirmed_archetype=archetype,
            feature_vector={k: float(v) for k, v in feature_vector.items()},
            shap_values=dict(sorted_feats),
            timestamp=datetime.now(timezone.utc),
        )

        try:
            result = await ingest_signal(payload)
            ingest_ids.append(result["ingest_id"])
            print(
                f"[bulk_load_seeds] queued {archetype:25s} → ingest_id={result['ingest_id'][:8]}..."
            )
        except DuplicateIngestError as e:
            print(f"[bulk_load_seeds] SKIP (dup)  {archetype:25s} → {e.existing_ingest_id[:8]}...")
        except QueueFullError:
            print(f"[bulk_load_seeds] SKIP (full) {archetype:25s} — queue at capacity", file=sys.stderr)
        except Exception as exc:
            print(f"[bulk_load_seeds] ERROR        {archetype:25s} — {exc}", file=sys.stderr)

    print(f"[bulk_load_seeds] Done. {len(ingest_ids)}/{len(seeds)} archetypes queued.")
    return ingest_ids


async def run_bulk_load(seeds_path: Path | None = None) -> list[str]:
    """Public coroutine — callable from app startup or standalone script."""
    if seeds_path is None:
        seeds_path = _ROOT / "data" / "computed_archetype_seeds.json"
    return await _bulk_load(seeds_path)


if __name__ == "__main__":
    # Standalone usage: python scripts/bulk_load_seeds.py [optional/path/to/seeds.json]
    import argparse

    parser = argparse.ArgumentParser(description="Bulk-load archetype seeds into the Red Team pipeline.")
    parser.add_argument(
        "--seeds",
        type=Path,
        default=_ROOT / "data" / "computed_archetype_seeds.json",
        help="Path to computed_archetype_seeds.json (default: data/computed_archetype_seeds.json)",
    )
    args = parser.parse_args()

    asyncio.run(run_bulk_load(args.seeds))
