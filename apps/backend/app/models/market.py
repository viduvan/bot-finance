"""Market data models: candles and snapshots."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, Index, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class MarketCandle(Base, TimestampMixin):
    """OHLCV candlestick data from Binance."""

    __tablename__ = "market_candles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)
    open_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    close_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    open: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    volume: Mapped[Decimal] = mapped_column(Numeric(30, 8), nullable=False)
    quote_volume: Mapped[Decimal | None] = mapped_column(Numeric(30, 8), nullable=True)
    trades_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="BINANCE")

    __table_args__ = (
        Index("idx_candles_symbol_tf_time", "symbol", "timeframe", open_time.desc()),
        Index("uq_candle", "symbol", "timeframe", "open_time", unique=True),
    )


class MarketSnapshot(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Point-in-time market state for a symbol."""

    __tablename__ = "market_snapshots"

    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(20), default="BINANCE")
    last_price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    best_bid: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    best_ask: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    bid_qty: Mapped[Decimal | None] = mapped_column(Numeric(30, 8), nullable=True)
    ask_qty: Mapped[Decimal | None] = mapped_column(Numeric(30, 8), nullable=True)
    spread_bps: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    volume_24h: Mapped[Decimal | None] = mapped_column(Numeric(30, 8), nullable=True)
    is_stale: Mapped[bool] = mapped_column(Boolean, default=False)
    validation_errors: Mapped[dict] = mapped_column(JSONB, default=list)
