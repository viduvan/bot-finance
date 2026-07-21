"""Market data API endpoints.

REST endpoints for candles, tickers, order book, snapshots,
data quality, and exchange info.
"""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends, Query

from app.dependencies import CurrentUser, DBSession
from app.market_data.binance_rest import binance_client
from app.market_data.service import MarketDataService
from app.schemas.market import (
    CandleListResponse,
    CandleResponse,
    DataQualityReport,
    MarketSnapshotResponse,
    OrderBookResponse,
    OrderBookLevel,
    SymbolInfo,
    TickerResponse,
)

logger = structlog.get_logger(__name__)
router = APIRouter()


def _get_market_service(db: DBSession) -> MarketDataService:
    return MarketDataService(db)


# ── Candles ──────────────────────────────────────────────────────


@router.get("/candles", response_model=CandleListResponse)
async def get_candles(
    user: CurrentUser,
    db: DBSession,
    symbol: str = Query(default="BTCUSDT", description="Trading pair"),
    timeframe: str = Query(default="15m", description="Candle timeframe"),
    limit: int = Query(default=100, ge=1, le=1000),
) -> CandleListResponse:
    """Get OHLCV candle data from database."""
    service = _get_market_service(db)
    candles = await service.get_candles(symbol, timeframe, limit)

    return CandleListResponse(
        symbol=symbol,
        timeframe=timeframe,
        count=len(candles),
        candles=[
            CandleResponse(
                symbol=c.symbol,
                timeframe=c.timeframe,
                open_time=c.open_time,
                close_time=c.close_time,
                open=c.open,
                high=c.high,
                low=c.low,
                close=c.close,
                volume=c.volume,
                quote_volume=c.quote_volume,
                trades_count=c.trades_count,
            )
            for c in candles
        ],
    )


@router.post("/candles/fetch")
async def fetch_candles(
    user: CurrentUser,
    db: DBSession,
    symbol: str = Query(default="BTCUSDT"),
    timeframe: str = Query(default="15m"),
    limit: int = Query(default=500, ge=1, le=1000),
) -> dict:
    """Fetch candles from Binance and store in database (manual trigger)."""
    service = _get_market_service(db)
    result = await service.fetch_and_store_candles(symbol, timeframe, limit)
    return {
        "status": "ok",
        "symbol": symbol,
        "timeframe": timeframe,
        "candles_stored": result["count"],
        "quality": result["quality"],
    }


@router.post("/candles/initial-load")
async def initial_data_load(
    user: CurrentUser,
    db: DBSession,
    symbol: str = Query(default="BTCUSDT"),
) -> dict:
    """Load initial historical data for all timeframes (manual trigger)."""
    service = _get_market_service(db)
    results = await service.initial_data_load(symbol)
    return {"status": "ok", "symbol": symbol, "results": results}


# ── Ticker ───────────────────────────────────────────────────────


@router.get("/ticker/{symbol}", response_model=TickerResponse)
async def get_ticker(
    symbol: str,
    user: CurrentUser,
) -> TickerResponse:
    """Get real-time ticker price from Binance."""
    data = await binance_client.get_ticker_24h(symbol)
    bid = data["bid"]
    ask = data["ask"]
    mid = (bid + ask) / 2 if (bid + ask) > 0 else bid
    spread_bps = ((ask - bid) / mid * 10000) if mid > 0 else 0

    return TickerResponse(
        symbol=data["symbol"],
        price=data["price"],
        bid=bid,
        ask=ask,
        bid_qty=data["bid_qty"],
        ask_qty=data["ask_qty"],
        spread_bps=spread_bps,
        volume_24h=data["volume_24h"],
        price_change_24h=data["price_change_24h"],
        price_change_pct_24h=data["price_change_pct_24h"],
        timestamp=data["timestamp"],
    )


# ── Order Book ───────────────────────────────────────────────────


@router.get("/orderbook/{symbol}", response_model=OrderBookResponse)
async def get_order_book(
    symbol: str,
    user: CurrentUser,
    limit: int = Query(default=20, ge=5, le=500),
) -> OrderBookResponse:
    """Get order book depth from Binance."""
    data = await binance_client.get_depth(symbol, limit)
    return OrderBookResponse(
        symbol=symbol,
        timestamp=data["timestamp"],
        bids=[OrderBookLevel(price=b["price"], quantity=b["quantity"]) for b in data["bids"]],
        asks=[OrderBookLevel(price=a["price"], quantity=a["quantity"]) for a in data["asks"]],
        last_update_id=data.get("last_update_id"),
    )


# ── Snapshots ────────────────────────────────────────────────────


@router.get("/snapshot/{symbol}", response_model=MarketSnapshotResponse | None)
async def get_latest_snapshot(
    symbol: str,
    user: CurrentUser,
    db: DBSession,
) -> MarketSnapshotResponse | dict:
    """Get the latest market snapshot from database."""
    service = _get_market_service(db)
    snapshot = await service.get_latest_snapshot(symbol)
    if not snapshot:
        return {"message": f"No snapshot available for {symbol}. Trigger /snapshot/{symbol}/refresh first."}
    return MarketSnapshotResponse(**snapshot)


@router.post("/snapshot/{symbol}/refresh")
async def refresh_snapshot(
    symbol: str,
    user: CurrentUser,
    db: DBSession,
) -> dict:
    """Build a fresh market snapshot from Binance (manual trigger)."""
    service = _get_market_service(db)
    snapshot = await service.build_and_save_snapshot(symbol)
    return {
        "status": "ok",
        "symbol": symbol,
        "price": str(snapshot["last_price"]),
        "spread_bps": str(snapshot["spread_bps"]),
        "quality": snapshot.get("data_quality", "GOOD"),
    }


# ── Data Quality ─────────────────────────────────────────────────


@router.get("/quality/{symbol}")
async def check_data_quality(
    symbol: str,
    user: CurrentUser,
    db: DBSession,
    timeframe: str = Query(default="15m"),
) -> dict:
    """Check data quality for a symbol/timeframe."""
    service = _get_market_service(db)
    return await service.check_data_quality(symbol, timeframe)


@router.post("/backfill/{symbol}")
async def backfill_gaps(
    symbol: str,
    user: CurrentUser,
    db: DBSession,
    timeframe: str = Query(default="15m"),
    hours_back: int = Query(default=24, ge=1, le=168),
) -> dict:
    """Backfill candle data gaps from Binance REST API."""
    service = _get_market_service(db)
    return await service.backfill_gaps(symbol, timeframe, hours_back)


# ── Exchange Info ────────────────────────────────────────────────


@router.get("/exchange-info/{symbol}", response_model=SymbolInfo)
async def get_exchange_info(
    symbol: str,
    user: CurrentUser,
) -> SymbolInfo:
    """Get trading rules for a symbol from Binance."""
    info = await binance_client.get_exchange_info(symbol)
    return SymbolInfo(**info)
