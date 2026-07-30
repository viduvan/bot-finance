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
            "fallback_chain": settings.llm_fallback_chain_list,
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
    """System status including dynamic service connectivity checks."""
    # Database check
    db_status = "disconnected"
    try:
        from sqlalchemy import text
        from app.database.session import engine
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
            db_status = "connected"
    except Exception as e:
        logger.warning("status_db_check_failed", error=str(e))

    # Redis check
    redis_status = "disconnected"
    try:
        import redis.asyncio as redis
        r = redis.from_url(settings.redis_url)
        if await r.ping():
            redis_status = "connected"
        await r.aclose()
    except Exception as e:
        logger.warning("status_redis_check_failed", error=str(e))

    # LLM check — ping the primary provider
    llm_status = "disconnected"
    primary = settings.llm_fallback_chain_list[0] if settings.llm_fallback_chain_list else "ollama"
    try:
        if primary == "ollama":
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as c:
                resp = await c.get(f"{settings.ollama_base_url}/api/tags")
                if resp.status_code == 200:
                    llm_status = "connected"
        elif primary == "gemini" and settings.gemini_api_key:
            llm_status = "connected"
        elif primary == "openai" and settings.openai_api_key:
            llm_status = "connected"
    except Exception as e:
        logger.warning("status_llm_check_failed", provider=primary, error=str(e))

    # Binance check
    binance_status = "disconnected"
    try:
        from app.market_data.binance_rest import binance_client
        res = await binance_client.get_ticker_price("BTCUSDT")
        if res and "price" in res:
            binance_status = "connected"
    except Exception as e:
        logger.warning("status_binance_check_failed", error=str(e))

    all_ok = (
        db_status == "connected"
        and redis_status == "connected"
        and llm_status == "connected"
        and binance_status == "connected"
    )

    return {
        "status": "operational" if all_ok else "degraded",
        "version": APP_VERSION,
        "trading_mode": settings.trading_mode.value,
        "timestamp": datetime.now(UTC).isoformat(),
        "services": {
            "database": db_status,
            "redis": redis_status,
            "llm": llm_status,
            "binance": binance_status,
        },
    }


@router.get("/license")
async def get_license() -> dict:
    """Return license and LLM integration info."""
    primary_provider = settings.llm_fallback_chain_list[0] if settings.llm_fallback_chain_list else "ollama"
    if primary_provider == "ollama":
        active_model = settings.ollama_model
        llm_status = "local"
    elif primary_provider == "gemini":
        active_model = settings.gemini_model
        llm_status = "connected" if settings.gemini_api_key else "not_configured"
    elif primary_provider == "openai":
        active_model = settings.openai_model
        llm_status = "connected" if settings.openai_api_key else "not_configured"
    else:
        active_model = "unknown"
        llm_status = "unknown"

    return {
        "app_name": settings.app_name,
        "version": APP_VERSION,
        "license": "MIT",
        "copyright": "Copyright (c) 2026 ChimSe",
        "llm_provider": primary_provider,
        "llm_model": active_model,
        "llm_status": llm_status,
        # Keep gemini_* keys for FE backward-compat until Phase 4 FE cleanup
        "gemini_model": active_model,
        "gemini_status": llm_status,
        "fallback_chain": settings.llm_fallback_chain_list,
        "rate_limits": {
            "rpm": 0 if primary_provider == "ollama" else 60,
            "tpm": 0 if primary_provider == "ollama" else 100_000,
            "rpd": 0 if primary_provider == "ollama" else 100,
        },
    }
