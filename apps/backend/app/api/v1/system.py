"""System API: health check, configuration, and status."""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from fastapi import APIRouter

from app.config import settings
from app.core.constants import APP_VERSION

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/config")
async def get_config() -> dict:
    """Return non-sensitive system configuration.

    NEVER exposes API keys, secrets, or passwords.
    """
    return {
        "app_name": settings.app_name,
        "version": APP_VERSION,
        "environment": settings.app_env.value,
        "trading": {
            "mode": settings.trading_mode.value,
            "exchange": settings.trading_exchange,
            "market": settings.trading_market,
            "symbols": settings.trading_symbols,
            "allowed_order_types": settings.trading_allowed_order_types,
        },
        "risk": {
            "risk_per_trade_percent": settings.risk_per_trade_percent,
            "max_daily_loss_percent": settings.max_daily_loss_percent,
            "max_total_exposure_percent": settings.max_total_exposure_percent,
            "max_open_positions": settings.max_open_positions,
            "min_risk_reward_ratio": settings.min_risk_reward_ratio,
            "max_spread_bps": settings.max_spread_bps,
            "max_price_drift_bps": settings.max_price_drift_bps,
        },
        "proposal": {
            "expiration_seconds": settings.proposal_expiration_seconds,
            "approval_token_expiration_seconds": settings.approval_token_expiration_seconds,
            "require_reconfirmation_on_edit": settings.require_reconfirmation_on_edit,
        },
        "agents": {
            "enabled": settings.agents_enabled,
            "max_iterations": settings.agent_max_iterations,
            "timeout_seconds": settings.agent_timeout_seconds,
        },
        "llm": {
            "fallback_chain": settings.llm_fallback_chain,
            "temperature": settings.llm_temperature,
        },
        "notifications": {
            "telegram_enabled": settings.telegram_enabled,
        },
        "monitoring": {
            "prometheus_enabled": settings.prometheus_enabled,
        },
        "mfa_enabled": settings.mfa_enabled,
        "server_time": datetime.now(UTC).isoformat(),
    }


@router.get("/status")
async def get_status() -> dict:
    """System status including service connectivity."""
    # Basic status - will be enhanced in later phases with actual connectivity checks
    return {
        "status": "operational",
        "version": APP_VERSION,
        "trading_mode": settings.trading_mode.value,
        "timestamp": datetime.now(UTC).isoformat(),
        "services": {
            "database": "connected",
            "redis": "connected",
            "llm": "unknown",
            "binance": "unknown",
        },
    }
