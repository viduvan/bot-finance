"""Pydantic schemas cho API dữ liệu thị trường (market data)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


# ── Lược đồ nến (Candle) ─────────────────────────────────────────


class CandleResponse(BaseModel):
    """Một nến OHLCV duy nhất."""

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
    """Danh sách nến kèm theo metadata."""

    symbol: str
    timeframe: str
    count: int
    candles: list[CandleResponse]


class CandleQueryParams(BaseModel):
    """Tham số query cho request lấy dữ liệu nến."""

    symbol: str = "BTCUSDT"
    timeframe: str = "15m"
    limit: int = Field(default=100, ge=1, le=1000)
    start_time: datetime | None = None
    end_time: datetime | None = None


# ── Lược đồ Ticker / Snapshot ────────────────────────────────────


class TickerResponse(BaseModel):
    """Giá ticker theo thời gian thực."""

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
    """Trạng thái thị trường tại một thời điểm cho một cặp giao dịch."""

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


# ── Lược đồ sổ lệnh (Order Book) ─────────────────────────────────


class OrderBookLevel(BaseModel):
    """Một mức giá duy nhất trong sổ lệnh."""

    price: Decimal
    quantity: Decimal


class OrderBookResponse(BaseModel):
    """Ảnh chụp nhanh độ sâu của sổ lệnh."""

    symbol: str
    timestamp: datetime
    bids: list[OrderBookLevel]
    asks: list[OrderBookLevel]
    last_update_id: int | None = None


# ── Lược đồ tin nhắn WebSocket ───────────────────────────────────


class WSTickerMessage(BaseModel):
    """Cập nhật ticker qua WebSocket đẩy xuống frontend."""

    type: str = "ticker"
    symbol: str
    price: str
    bid: str | None = None
    ask: str | None = None
    volume_24h: str | None = None
    timestamp: str


class WSKlineMessage(BaseModel):
    """Cập nhật nến (kline) qua WebSocket đẩy xuống frontend."""

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


# ── Thông tin sàn giao dịch (Exchange Info) ──────────────────────


class SymbolInfo(BaseModel):
    """Quy tắc giao dịch của một cặp tiền trên Binance."""

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


# ── Chất lượng dữ liệu (Data Quality) ────────────────────────────


class DataQualityReport(BaseModel):
    """Báo cáo về chất lượng dữ liệu của một cặp giao dịch."""

    symbol: str
    timeframe: str
    total_candles: int
    expected_candles: int
    missing_candles: int
    gap_count: int
    gaps: list[dict] = []
    staleness_seconds: float | None = None
    is_healthy: bool
