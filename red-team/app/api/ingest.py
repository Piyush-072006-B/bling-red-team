"""
API Router — POST /red-team/ingest
=====================================
Accepts FraudDNA | NoveltyEscalation | GateMissLog (discriminated union on source_type).
Protected by X-API-Key. Rate limited to 500/min via slowapi.
"""


from typing import Any


from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.config import get_settings
from app.ingest.router import DuplicateIngestError, QueueFullError, ingest_signal
from app.ingest.schemas import IngestPayload
from app.utils.audit_logger import get_logger
from app.utils.auth import require_api_key
from app.utils.limiter import limiter

log = get_logger(__name__)

router = APIRouter(
    prefix="/red-team",
    tags=["ingest"],
)


@router.post(
    "/ingest",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest a fraud signal from Blue Team",
    response_description="Ingest accepted — returns ingest_id, priority, and queue label",
)
@limiter.limit(get_settings().ingest_rate_limit)
async def ingest_endpoint(
    request: Request,
    payload: IngestPayload,
    _key: str = Depends(require_api_key),
) -> dict[str, Any]:
    """
    Accept a confirmed fraud signal from Blue Team.

    **source_type discriminator:**
    - `FRAUD_DNA`  — confirmed fraud transaction (account_id, feature_vector, shap_values)
    - `NOVELTY`    — structural novelty escalation (fingerprint_id, structural_features)
    - `GATE_MISS`  — gate miss log (transaction_id, gate_name, alert_id)

    Returns `ingest_id`, `priority` (LOW/MEDIUM/HIGH/CRITICAL), and `queued_for` label.
    Duplicate signals (same transaction_id or fingerprint_id) return **409 Conflict**.
    Rate limited to 500 requests/minute per IP.
    """
    try:
        result = await ingest_signal(payload)
        return result
    except DuplicateIngestError as exc:
        log.info(
            "ingest_conflict",
            existing_id=exc.existing_ingest_id,
            source_type=payload.source_type,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "duplicate_signal",
                "existing_ingest_id": exc.existing_ingest_id,
                "message": "A signal with the same identifier has already been ingested.",
            },
        )
    except QueueFullError:
        log.warning("ingest_queue_full", source_type=payload.source_type)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "queue_full",
                "message": "All priority queues are at capacity. Retry later.",
            },
        )
