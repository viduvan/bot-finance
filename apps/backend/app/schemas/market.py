"""Pydantic schemas for market data API."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


# ── Candle Schemas ───────────────────────────────────────────────


class CandleResponse(BaseModel):
    """Single OHLCV candle."""

    symbol: str
    timeframe: str
    open_time: datetime
    close_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    quote_volume: Decimal | None = None
    trades_count: int | None = None

    model_config = {"from_attributes": True}


class CandleListResponse(BaseModel):
    """List of candles with metadata."""

    symbol: str
    timeframe: str
    count: int
    candles: list[CandleResponse]


class CandleQueryParams(BaseModel):
    """Query parameters for candle requests."""

    symbol: str = "BTCUSDT"
    timeframe: str = "15m"
    limit: int = Field(default=100, ge=1, le=1000)
    start_time: datetime | None = None
    end_time: datetime | None = None


# ── Ticker / Snapshot Schemas ────────────────────────────────────


class TickerResponse(BaseModel):
    """Real-time ticker price."""

    symbol: str
    price: Decimal
    bid: Decimal | None = None
    ask: Decimal | None = None
    bid_qty: Decimal | None = None
    ask_qty: Decimal | None = None
    spread_bps: Decimal | None = None
    volume_24h: Decimal | None = None
    price_change_24h: Decimal | None = None
    price_change_pct_24h: Decimal | None = None
    timestamp: datetime


class MarketSnapshotResponse(BaseModel):
    """Point-in-time market state for a symbol."""

    id: str
    symbol: str
    timestamp: datetime
    source: str
    last_price: Decimal
    best_bid: Decimal | None = None
    best_ask: Decimal | None = None
    bid_qty: Decimal | None = None
    ask_qty: Decimal | None = None
    spread_bps: Decimal | None = None
    volume_24h: Decimal | None = None
    is_stale: bool = False

    model_config = {"from_attributes": True}


# ── Order Book Schemas ───────────────────────────────────────────


class OrderBookLevel(BaseModel):
    """Single price level in the order book."""

    price: Decimal
    quantity: Decimal


class OrderBookResponse(BaseModel):
    """Order book depth snapshot."""

    symbol: str
    timestamp: datetime
    bids: list[OrderBookLevel]
    asks: list[OrderBookLevel]
    last_update_id: int | None = None


# ── WebSocket Message Schemas ────────────────────────────────────


class WSTickerMessage(BaseModel):
    """WebSocket ticker update pushed to frontend."""

    type: str = "ticker"
    symbol: str
    price: str
    bid: str | None = None
    ask: str | None = None
    volume_24h: str | None = None
    timestamp: str


class WSKlineMessage(BaseModel):
    """WebSocket kline update pushed to frontend."""

    type: str = "kline"
    symbol: str
    timeframe: str
    open: str
    high: str
    low: str
    close: str
    volume: str
    is_closed: bool
    timestamp: str


# ── Exchange Info ────────────────────────────────────────────────


class SymbolInfo(BaseModel):
    """Binance symbol trading rules."""

    symbol: str
    status: str
    base_asset: str
    quote_asset: str
    price_precision: int
    quantity_precision: int
    min_notional: Decimal | None = None
    min_quantity: Decimal | None = None
    max_quantity: Decimal | None = None
    step_size: Decimal | None = None
    tick_size: Decimal | None = None


# ── Data Quality ─────────────────────────────────────────────────


class DataQualityReport(BaseModel):
    """Report on data quality for a symbol."""

    symbol: str
    timeframe: str
    total_candles: int
    expected_candles: int
    missing_candles: int
    gap_count: int
    gaps: list[dict] = []
    staleness_seconds: float | None = None
    is_healthy: bool
