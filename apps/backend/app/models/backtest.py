"""Backtest models."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, JSON_TYPE, TimestampMixin, UUIDPrimaryKeyMixin


class StrategyVersion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Versioned trading strategy configuration."""

    __tablename__ = "strategy_versions"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    config: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)


class BacktestRun(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Backtest execution and results."""

    __tablename__ = "backtest_runs"

    strategy_version_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("strategy_versions.id"), nullable=True
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    config: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="RUNNING")
    results: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BacktestTrade(Base, UUIDPrimaryKeyMixin):
    """Individual trade within a backtest."""

    __tablename__ = "backtest_trades"

    backtest_run_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("backtest_runs.id"), nullable=False, index=True
    )
    entry_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    exit_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    entry_price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    exit_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    fee: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    slippage: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    pnl: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    exit_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)
