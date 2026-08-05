"""Structured JSON logging configuration using structlog.

All logs include: request_id, service, timestamp, severity.
Trading-related logs additionally include: workflow_id, proposal_id, order_id.
Secrets are NEVER logged.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

from app.config import settings


def setup_logging() -> None:
    """Configure structured logging for the application.

    - Development: colored, human-readable console output
    - Production: JSON format for log aggregation
    """
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
        _secret_filter,
    ]

    if settings.app_env.value in ("development", "testing"):
        # Human-readable colored output for development
        renderer: structlog.types.Processor = structlog.dev.ConsoleRenderer(
            colors=True,
        )
    else:
        # JSON output for production log aggregation
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, settings.log_level.upper()))

    # Suppress noisy third-party loggers
    for logger_name in ("uvicorn.access", "httpx", "httpcore", "websockets"):
        logging.getLogger(logger_name).setLevel(logging.WARNING)


# ── Secret Filter ────────────────────────────────────────────────

_SECRET_KEYS = frozenset(
    {
        "password",
        "secret",
        "token",
        "api_key",
        "api_secret",
        "authorization",
        "cookie",
        "encryption_key",
        "jwt_secret",
        "approval_token_secret",
        "mfa_secret",
    }
)


def _secret_filter(logger: Any, method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Remove sensitive values from log output.

    Any key containing 'secret', 'password', 'token', 'api_key' etc.
    will have its value replaced with '[REDACTED]'.
    """
    for key in list(event_dict.keys()):
        key_lower = key.lower()
        if any(secret_key in key_lower for secret_key in _SECRET_KEYS):
            event_dict[key] = "[REDACTED]"
    return event_dict


def get_logger(name: str | None = None, **initial_context: Any) -> structlog.stdlib.BoundLogger:
    """Get a structured logger with optional initial context.

    Usage:
        logger = get_logger(__name__, service="risk_engine")
        logger.info("risk_check_passed", proposal_id="abc-123")
    """
    log: structlog.stdlib.BoundLogger = structlog.get_logger(name)
    if initial_context:
        log = log.bind(**initial_context)
    return log
