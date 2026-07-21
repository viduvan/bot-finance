"""Global error handler middleware.

Catches all exceptions and returns consistent JSON error responses.
Ensures no stack traces leak to clients in production.
"""

from __future__ import annotations

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import ORJSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import ACTAError

logger = structlog.get_logger(__name__)


def register_error_handlers(app: FastAPI) -> None:
    """Register all global exception handlers on the FastAPI app."""

    @app.exception_handler(ACTAError)
    async def acta_error_handler(request: Request, exc: ACTAError) -> ORJSONResponse:
        """Handle all ACTA business logic exceptions."""
        status_map: dict[str, int] = {
            "AUTH_FAILED": status.HTTP_401_UNAUTHORIZED,
            "MFA_REQUIRED": status.HTTP_401_UNAUTHORIZED,
            "MFA_INVALID": status.HTTP_401_UNAUTHORIZED,
            "TOKEN_EXPIRED": status.HTTP_401_UNAUTHORIZED,
            "FORBIDDEN": status.HTTP_403_FORBIDDEN,
            "NOT_FOUND": status.HTTP_404_NOT_FOUND,
            "PROPOSAL_NOT_FOUND": status.HTTP_404_NOT_FOUND,
            "ORDER_NOT_FOUND": status.HTTP_404_NOT_FOUND,
            "CONFLICT": status.HTTP_409_CONFLICT,
            "DUPLICATE_ORDER": status.HTTP_409_CONFLICT,
            "RATE_LIMITED": status.HTTP_429_TOO_MANY_REQUESTS,
            "INVALID_STATE_TRANSITION": status.HTTP_422_UNPROCESSABLE_ENTITY,
            "RISK_REJECTED": status.HTTP_422_UNPROCESSABLE_ENTITY,
            "APPROVAL_TOKEN_INVALID": status.HTTP_422_UNPROCESSABLE_ENTITY,
            "APPROVAL_TOKEN_USED": status.HTTP_422_UNPROCESSABLE_ENTITY,
            "PROPOSAL_EXPIRED": status.HTTP_422_UNPROCESSABLE_ENTITY,
            "INSUFFICIENT_BALANCE": status.HTTP_422_UNPROCESSABLE_ENTITY,
            "PRICE_DRIFT": status.HTTP_422_UNPROCESSABLE_ENTITY,
            "EXECUTION_DENIED": status.HTTP_403_FORBIDDEN,
            "STALE_DATA": status.HTTP_503_SERVICE_UNAVAILABLE,
            "BINANCE_ERROR": status.HTTP_502_BAD_GATEWAY,
            "LLM_UNAVAILABLE": status.HTTP_503_SERVICE_UNAVAILABLE,
            "EXTERNAL_SERVICE_ERROR": status.HTTP_502_BAD_GATEWAY,
            "AGENT_TIMEOUT": status.HTTP_504_GATEWAY_TIMEOUT,
            "AGENT_OUTPUT_INVALID": status.HTTP_422_UNPROCESSABLE_ENTITY,
            "CONFIG_ERROR": status.HTTP_500_INTERNAL_SERVER_ERROR,
        }

        http_status = status_map.get(exc.error_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

        logger.warning(
            "business_error",
            error_code=exc.error_code,
            message=exc.message,
            status_code=http_status,
        )

        return ORJSONResponse(
            status_code=http_status,
            content={
                "error": {
                    "code": exc.error_code,
                    "message": exc.message,
                }
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> ORJSONResponse:
        """Handle standard HTTP exceptions."""
        return ORJSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": "HTTP_ERROR",
                    "message": str(exc.detail),
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> ORJSONResponse:
        """Handle Pydantic validation errors with clean output."""
        errors = []
        for error in exc.errors():
            field = " → ".join(str(loc) for loc in error.get("loc", []))
            errors.append({
                "field": field,
                "message": error.get("msg", ""),
                "type": error.get("type", ""),
            })

        return ORJSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed",
                    "details": errors,
                }
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> ORJSONResponse:
        """Catch-all for unhandled exceptions.

        Logs full traceback but returns generic error to client.
        Never exposes internal details in production.
        """
        logger.error(
            "unhandled_exception",
            exc_type=type(exc).__name__,
            exc_message=str(exc),
            exc_info=True,
        )

        return ORJSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred",
                }
            },
        )
