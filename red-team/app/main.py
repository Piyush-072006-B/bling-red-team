"""
Red Team FastAPI Application Entry Point
=========================================
Wires all routers, auth middleware, health endpoint, and rate limiting.

Endpoints:
  POST /red-team/ingest              — ingest fraud signals (rate limited: 500/min)
  GET  /red-team/report/{id}         — full evasion analysis for an ingest
  GET  /red-team/evasions            — paginated evasion KB listing
  GET  /red-team/briefing            — developer intelligence briefing
  GET  /red-team/attack-graph/{id}   — TGEP graph packages for an ingest
  GET  /health                       — service health check (no auth)
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api import attack_graph as attack_graph_router
from app.api import briefing as briefing_router
from app.api import evasions as evasions_router
from app.api import ingest as ingest_router
from app.api import report as report_router
from app.config import get_settings
from app.utils.audit_logger import configure_logging, get_logger
from app.utils.limiter import limiter
from app.worker.pipeline import worker_loop

log = get_logger(__name__)


# limiter is imported from app.utils.limiter — see that module for docs.


# ─────────────────────────────────────────────────────────────────────────────
# Lifespan
# ─────────────────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    configure_logging()
    settings = get_settings()
    log.info(
        "red_team_starting",
        env=settings.app_env,
        shadow_url=settings.blue_team_shadow_url,
    )

    # Start the background worker pipeline
    worker_task = asyncio.create_task(worker_loop(), name="red_team_worker")
    log.info("worker_task_started")

    # Start the self-generation loop (generates patterns when Blue Team is offline)
    from app.engines.self_generator import start_self_generation_loop
    self_gen_task = asyncio.create_task(
        start_self_generation_loop(
            interval_seconds=settings.self_generation_interval_seconds,
            enabled=settings.self_generation_enabled,
        ),
        name="red_team_self_gen",
    )
    log.info("self_gen_task_started")

    # Bulk-load archetype seeds on startup if configured
    if settings.bulk_load_on_startup:
        from scripts.bulk_load_seeds import run_bulk_load
        asyncio.create_task(run_bulk_load(), name="red_team_bulk_load")
        log.info("bulk_load_task_started")

    yield

    # Graceful shutdown: cancel both tasks and wait for them to finish
    self_gen_task.cancel()
    worker_task.cancel()
    try:
        await self_gen_task
    except asyncio.CancelledError:
        pass
    try:
        await worker_task
    except asyncio.CancelledError:
        pass
    log.info("red_team_shutting_down")


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI app
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="BLING Red Team API",
    description=(
        "Adversarial simulation engine for BLING forensic fraud detection. "
        "Receives confirmed fraud signals from Blue Team, mutates them to find "
        "detection blind spots, and proposes patches. "
        "**Output is developer intelligence only — never automated blocking.**"
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── State (required by slowapi) ───────────────────────────────────────────────
app.state.limiter = limiter

# ── Exception handlers ────────────────────────────────────────────────────────
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── Middleware ─────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten in production
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────────────────────
# Routers
# ─────────────────────────────────────────────────────────────────────────────

app.include_router(ingest_router.router)
app.include_router(report_router.router)
app.include_router(evasions_router.router)
app.include_router(briefing_router.router)
app.include_router(attack_graph_router.router)


# ─────────────────────────────────────────────────────────────────────────────
# Health endpoint (no auth — used by Docker healthcheck and load balancers)
# ─────────────────────────────────────────────────────────────────────────────


@app.get(
    "/health",
    tags=["health"],
    summary="Service health check",
    include_in_schema=True,
)
async def health() -> dict[str, str]:
    """Returns service liveness. No authentication required."""
    return {"status": "ok", "service": "red-team"}


# ─────────────────────────────────────────────────────────────────────────────
# Entry point for uvicorn
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8002,
        reload=True,
        log_level="info",
    )
