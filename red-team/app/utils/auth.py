"""
Auth Middleware — X-API-Key Header Verification
================================================
Validates the X-API-Key header on every protected route.
Key is read from RED_TEAM_API_KEY environment variable via Settings.
Returns HTTP 403 on mismatch or missing header.

Usage (in route file):
    from app.utils.auth import require_api_key
    router = APIRouter(dependencies=[Depends(require_api_key)])
"""

from __future__ import annotations

import secrets

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.config import get_settings
from app.utils.audit_logger import get_logger

log = get_logger(__name__)

# FastAPI security scheme — documents the header in OpenAPI
_api_key_header_scheme = APIKeyHeader(
    name="X-API-Key",
    auto_error=False,  # We raise our own 403 with a consistent message
    description="Red Team API key. Set RED_TEAM_API_KEY in environment.",
)


async def require_api_key(
    api_key: str | None = Security(_api_key_header_scheme),
) -> str:
    """
    FastAPI dependency that validates the X-API-Key header.

    Returns the validated key string on success.
    Raises HTTP 403 on missing or invalid key.

    Usage:
        router = APIRouter(dependencies=[Depends(require_api_key)])
    or per-route:
        @router.post("/endpoint")
        async def endpoint(key: str = Depends(require_api_key)):
            ...
    """
    settings = get_settings()
    expected_key = settings.red_team_api_key

    if api_key is None:
        log.warning("auth_rejected", reason="missing_header")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing X-API-Key header",
        )

    # Constant-time comparison to prevent timing attacks
    if not secrets.compare_digest(api_key, expected_key):
        log.warning("auth_rejected", reason="invalid_key")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )

    return api_key
