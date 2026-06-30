"""
Audit Logger — Structured Logging (No PII)
==========================================
Configures structlog for structured JSON logging.

Rules:
  - Never log raw account IDs, VPAs, or transaction IDs.
  - Hash all identifiers: sha256(SALT + value)[:12]
  - Use get_logger(__name__) in every module.
"""

from __future__ import annotations

import hashlib
import logging
import sys

import structlog

from app.config import get_settings


def configure_logging() -> None:
    """Call once at application startup (in app/main.py lifespan)."""
    settings = get_settings()
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.app_env == "development":
        # Human-readable in dev
        renderer = structlog.dev.ConsoleRenderer()
    else:
        # JSON in staging / production
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=shared_processors + [renderer],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Also configure stdlib logging so uvicorn / sqlalchemy logs go through structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structlog bound logger for the given module name."""
    return structlog.get_logger(name)


def hash_id(raw_id: str) -> str:
    """
    Hash a sensitive identifier using SHA-256 + configured salt.
    Returns first 12 hex chars — sufficient for correlation, not reversible.

    Usage:
        log.info("ingest received", account=hash_id(account_id))
    """
    salt = get_settings().pii_hash_salt
    return hashlib.sha256(f"{salt}{raw_id}".encode()).hexdigest()[:12]
