"""ACTA - FastAPI application entry point.

Human-in-the-Loop Multi-Agent Crypto Trading Advisory System.

Principle: Agents analyze. Agents advise. Humans decide.
Only approved orders may execute.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from app.config import settings
from app.core.constants import APP_DESCRIPTION, APP_NAME, APP_VERSION
from app.core.logging import setup_logging
from app.core.metrics import SYSTEM_UP
from app.database.session import close_db, init_db
from app.services.telegram_service import telegram_service

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown lifecycle."""
    # ── Startup ──────────────────────────────────────────────
    setup_logging()
    logger.info("starting_application", env=settings.app_env.value, mode=settings.trading_mode.value)

    # Initialize database
    await init_db()
    logger.info("database_connected")

    # Set system up metric
    SYSTEM_UP.set(1)

    logger.info(
        "application_ready",
        trading_mode=settings.trading_mode.value,
        symbols=settings.trading_symbols,
        mfa_enabled=settings.mfa_enabled,
    )

    yield

    # ── Shutdown ─────────────────────────────────────────────
    logger.info("shutting_down_application")
    SYSTEM_UP.set(0)
    await telegram_service.close()
    await close_db()
    logger.info("application_stopped")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=APP_NAME,
        description=APP_DESCRIPTION,
        version=APP_VERSION,
        lifespan=lifespan,
        default_response_class=ORJSONResponse,
        docs_url="/api/docs" if settings.debug else None,
        redoc_url="/api/redoc" if settings.debug else None,
    )

    # ── Middleware ────────────────────────────────────────────

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Prometheus instrumentation
    if settings.prometheus_enabled:
        Instrumentator(
            should_group_status_codes=True,
            should_ignore_untemplated=True,
            excluded_handlers=["/metrics", "/api/v1/system/health"],
        ).instrument(app).expose(app, endpoint="/metrics")

    # Global error handlers
    from app.api.middleware.error_handler import register_error_handlers
    register_error_handlers(app)

    # Rate limiting
    from app.api.middleware.rate_limit import register_rate_limiter
    register_rate_limiter(app)

    # ── Routes ───────────────────────────────────────────────

    # Health check (no auth required)
    @app.get("/api/v1/system/health", tags=["system"])
    async def health_check() -> dict:
        """System health check endpoint."""
        return {
            "status": "healthy",
            "version": APP_VERSION,
            "environment": settings.app_env.value,
            "trading_mode": settings.trading_mode.value,
        }

    # Request ID middleware
    @app.middleware("http")
    async def add_request_id(request: Request, call_next):  # type: ignore[no-untyped-def]
        """Add unique request ID to every request for tracing."""
        import uuid
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    # Import and register API routers
    from app.api.v1.auth import router as auth_router
    from app.api.v1.system import router as system_router

    app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
    app.include_router(system_router, prefix="/api/v1/system", tags=["system"])

    return app


# Application instance
app = create_app()
