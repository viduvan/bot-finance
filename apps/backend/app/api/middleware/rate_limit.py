"""Rate limiting middleware using slowapi.

Protects API from abuse with configurable limits per endpoint group.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import ORJSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import settings


def _key_func(request: Request) -> str:
    """Rate limit key: use real IP or forwarded IP."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)


# Global limiter instance
limiter = Limiter(
    key_func=_key_func,
    default_limits=[settings.rate_limit_default],
    storage_uri=settings.redis_url,
    strategy="fixed-window",
)


def register_rate_limiter(app: FastAPI) -> None:
    """Register rate limiter on the FastAPI app."""
    app.state.limiter = limiter

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> ORJSONResponse:
        return ORJSONResponse(
            status_code=429,
            content={
                "error": {
                    "code": "RATE_LIMITED",
                    "message": f"Rate limit exceeded: {exc.detail}",
                }
            },
        )
