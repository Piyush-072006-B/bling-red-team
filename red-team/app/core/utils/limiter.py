"""
Rate Limiter — Shared slowapi Limiter Singleton
=================================================
Provides a single Limiter instance that can be imported by both app/main.py
(to register with the FastAPI app) and route modules (to apply decorators)
without creating circular imports.

Usage in a route:
    from app.core.utils.limiter import limiter
    @limiter.limit("500/minute")
    async def my_endpoint(request: Request, ...): ...
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
