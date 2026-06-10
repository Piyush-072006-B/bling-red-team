"""
Configuration — Red Team Service
==================================
Loads all settings from environment variables using pydantic-settings.
Provides a cached settings singleton via get_settings().
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Security ──────────────────────────────────────────────────
    red_team_api_key: str = Field(
        default="changeme",
        description="X-API-Key secret for authenticating inbound requests",
    )

    # Salt used when hashing account IDs / VPAs before storage or logging.
    # Override in production — never leave as default.
    pii_hash_salt: str = Field(
        default="red-team-salt-changeme",
        description="Salt for sha256(SALT+account_id)[:12] PII masking",
    )

    # ── Blue Team integration ──────────────────────────────────────
    blue_team_shadow_api_key: str = Field(
        default="",
        description="Used as X-API-Key when calling Blue Team shadow scorer",
    )
    blue_team_shadow_url: str = Field(
        default="",
        description=(
            "Base URL for Blue Team shadow scorer. MUST point to Blue Team service. "
            "Leave empty to disable — scorer will return null scores immediately "
            "without making any HTTP call."
        ),
    )
    blue_team_ingest_url: str = Field(
        default="http://localhost:8000/api/v1",
        description="Blue Team main API base URL (reference only)",
    )

    # ── TGEP webhook ──────────────────────────────────────────────
    tgep_webhook_url: str = Field(
        default="http://localhost:9000/api/red-team/evaluate",
        description="TGEP endpoint for patch proposal webhooks",
    )

    # ── Database ──────────────────────────────────────────────────
    postgres_url: str = Field(
        default="postgresql://redteam:redteam@localhost:5433/redteam",
        description="Sync PostgreSQL URL (psycopg2 driver, used by Alembic)",
    )
    postgres_async_url: str = Field(
        default="postgresql+asyncpg://redteam:redteam@localhost:5433/redteam",
        description="Async PostgreSQL URL (asyncpg driver, used by SQLAlchemy async engine)",
    )

    # ── Redis ─────────────────────────────────────────────────────
    redis_url: str = Field(
        default="redis://localhost:6380",
        description="Redis URL for queuing and caching",
    )

    # ── App ───────────────────────────────────────────────────────
    app_env: str = Field(
        default="development",
        description="Environment tag: development | staging | production",
    )
    log_level: str = Field(
        default="INFO",
        description="Log level: DEBUG | INFO | WARNING | ERROR",
    )

    # ── Rate limiting ─────────────────────────────────────────────
    ingest_rate_limit: str = Field(
        default="500/minute",
        description="slowapi rate limit string for POST /red-team/ingest",
    )

    # ── Queue sizing ──────────────────────────────────────────────
    ingest_queue_max_size: int = Field(
        default=1000,
        description="Max items per priority queue tier. Returns 503 when full.",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings singleton. Re-loads from env on first call."""
    return Settings()
