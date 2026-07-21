"""Application configuration using Pydantic Settings.

All config is loaded from environment variables or .env file.
Secrets are never logged or exposed via API.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


class TradingMode(str, Enum):
    BACKTEST = "BACKTEST"
    PAPER = "PAPER"
    LIVE = "LIVE"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_nested_delimiter="__",
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────
    app_name: str = "ACTA"
    app_env: Environment = Environment.DEVELOPMENT
    app_timezone: str = "Asia/Bangkok"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # ── Server ───────────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1
    log_level: str = "info"

    # ── Database ─────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://acta:acta_secret@localhost:5432/acta"
    database_pool_size: int = 10
    database_max_overflow: int = 20
    database_echo: bool = False

    # ── Redis ────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    redis_cache_ttl: int = 300  # seconds

    # ── Celery ───────────────────────────────────────────────────
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # ── JWT ──────────────────────────────────────────────────────
    jwt_secret: str = "CHANGE-ME-IN-PRODUCTION-use-openssl-rand-hex-32"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # ── Security ─────────────────────────────────────────────────
    approval_token_secret: str = "CHANGE-ME-approval-token-secret"
    encryption_key: str = "CHANGE-ME-32-byte-encryption-key-here"
    password_min_length: int = 12
    rate_limit_default: str = "60/minute"
    rate_limit_auth: str = "10/minute"
    mfa_enabled: bool = True
    mfa_issuer_name: str = "ACTA Trading"

    # ── Trading ──────────────────────────────────────────────────
    trading_mode: TradingMode = TradingMode.PAPER
    trading_exchange: str = "BINANCE"
    trading_market: str = "SPOT"
    trading_symbols: list[str] = Field(default=["BTCUSDT", "ETHUSDT"])
    trading_allowed_order_types: list[str] = Field(default=["LIMIT", "MARKET"])

    # ── Risk ─────────────────────────────────────────────────────
    risk_per_trade_percent: float = 0.5
    max_daily_loss_percent: float = 2.0
    max_total_exposure_percent: float = 20.0
    max_open_positions: int = 2
    min_risk_reward_ratio: float = 2.0
    max_spread_bps: float = 10.0
    max_price_drift_bps: float = 20.0

    # ── Proposal ─────────────────────────────────────────────────
    proposal_expiration_seconds: int = 600
    approval_token_expiration_seconds: int = 30
    require_reconfirmation_on_edit: bool = True

    # ── Agents ───────────────────────────────────────────────────
    agents_enabled: list[str] = Field(
        default=["market_regime", "technical", "order_flow", "risk_analysis", "critic"]
    )
    agent_max_iterations: int = 2
    agent_timeout_seconds: int = 60
    agent_max_tool_calls: int = 5

    # ── LLM ──────────────────────────────────────────────────────
    # Ollama (primary - local)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:14b"
    ollama_timeout: int = 30

    # Gemini (fallback 1)
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    gemini_timeout: int = 15

    # OpenAI (fallback 2)
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_timeout: int = 15

    llm_temperature: float = 0.1
    llm_fallback_chain: list[str] = Field(default=["ollama", "gemini", "openai"])

    # ── Binance ──────────────────────────────────────────────────
    binance_read_api_key: str = ""
    binance_read_api_secret: str = ""
    binance_trade_api_key: str = ""
    binance_trade_api_secret: str = ""
    binance_testnet: bool = True
    binance_base_url: str = "https://api.binance.com"
    binance_ws_url: str = "wss://stream.binance.com:9443/ws"
    binance_testnet_base_url: str = "https://testnet.binance.vision"
    binance_testnet_ws_url: str = "wss://testnet.binance.vision/ws"

    # ── Notifications ────────────────────────────────────────────
    telegram_enabled: bool = False
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # ── Monitoring ───────────────────────────────────────────────
    prometheus_enabled: bool = True

    # ── Analysis Schedule ────────────────────────────────────────
    analysis_schedule_enabled: bool = True
    analysis_interval_minutes: int = 15  # Run analysis every 15 minutes

    @field_validator("trading_mode", mode="before")
    @classmethod
    def validate_trading_mode(cls, v: Any) -> Any:
        """Ensure system defaults to PAPER mode for safety."""
        if isinstance(v, str):
            v = v.upper()
        return v

    @property
    def is_live(self) -> bool:
        """Check if system is in live trading mode."""
        return self.trading_mode == TradingMode.LIVE

    @property
    def is_paper(self) -> bool:
        """Check if system is in paper trading mode."""
        return self.trading_mode == TradingMode.PAPER

    @property
    def binance_active_base_url(self) -> str:
        """Return appropriate Binance base URL based on testnet setting."""
        if self.binance_testnet:
            return self.binance_testnet_base_url
        return self.binance_base_url

    @property
    def binance_active_ws_url(self) -> str:
        """Return appropriate Binance WebSocket URL based on testnet setting."""
        if self.binance_testnet:
            return self.binance_testnet_ws_url
        return self.binance_ws_url


# Singleton instance
settings = Settings()
