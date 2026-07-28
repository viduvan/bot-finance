"""API endpoints dữ liệu thị trường.

Các REST endpoints cho nến (candles), tickers, sổ lệnh (order book), ảnh chụp nhanh (snapshots),
chất lượng dữ liệu và thông tin sàn.
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


# ── Nến (Candles) ──────────────────────────────────────────────────────


@router.get("/candles", response_model=CandleListResponse)
async def get_candles(
    user: CurrentUser,
    db: DBSession,
    symbol: str = Query(default="BTCUSDT", description="Cặp giao dịch"),
    timeframe: str = Query(default="15m", description="Khung thời gian nến"),
    limit: int = Query(default=100, ge=1, le=1000),
) -> CandleListResponse:
    """Lấy dữ liệu nến OHLCV từ cơ sở dữ liệu."""
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
    """Lấy dữ liệu nến từ Binance và lưu vào cơ sở dữ liệu (kích hoạt thủ công)."""
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
    """Tải dữ liệu lịch sử ban đầu cho tất cả các khung thời gian (kích hoạt thủ công)."""
    service = _get_market_service(db)
    results = await service.initial_data_load(symbol)
    return {"status": "ok", "symbol": symbol, "results": results}


# ── Ticker ───────────────────────────────────────────────────────


@router.get("/ticker/{symbol}", response_model=TickerResponse)
async def get_ticker(
    symbol: str,
    user: CurrentUser,
) -> TickerResponse:
    """Lấy giá ticker theo thời gian thực từ Binance."""
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


# ── Sổ lệnh (Order Book) ───────────────────────────────────────────────────


@router.get("/orderbook/{symbol}", response_model=OrderBookResponse)
async def get_order_book(
    symbol: str,
    user: CurrentUser,
    limit: int = Query(default=20, ge=5, le=500),
) -> OrderBookResponse:
    """Lấy độ sâu sổ lệnh từ Binance."""
    data = await binance_client.get_depth(symbol, limit)
    return OrderBookResponse(
        symbol=symbol,
        timestamp=data["timestamp"],
        bids=[OrderBookLevel(price=b["price"], quantity=b["quantity"]) for b in data["bids"]],
        asks=[OrderBookLevel(price=a["price"], quantity=a["quantity"]) for a in data["asks"]],
        last_update_id=data.get("last_update_id"),
    )


# ── Ảnh chụp nhanh (Snapshots) ────────────────────────────────────────────────────


@router.get("/snapshot/{symbol}")
async def get_latest_snapshot(
    symbol: str,
    user: CurrentUser,
    db: DBSession,
) -> dict:
    """Lấy ảnh chụp nhanh thị trường gần nhất từ cơ sở dữ liệu."""
    service = _get_market_service(db)
    try:
        snapshot = await service.get_latest_snapshot(symbol)
    except Exception as e:
        logger.error("snapshot_fetch_failed", symbol=symbol, error=str(e))
        return {"message": f"Không thể lấy snapshot: {e}"}
    if not snapshot:
        return {"message": f"Không có ảnh chụp nhanh cho {symbol}. Hãy kích hoạt /snapshot/{symbol}/refresh trước."}
    # Trả về an toàn dưới dạng dict (tránh crash khi thiếu field)
    return {
        "id": snapshot.get("id", ""),
        "symbol": snapshot.get("symbol", symbol),
        "timestamp": str(snapshot.get("timestamp", "")),
        "source": snapshot.get("source", ""),
        "last_price": str(snapshot.get("last_price", "0")),
        "best_bid": str(snapshot.get("best_bid", "0")) if snapshot.get("best_bid") else None,
        "best_ask": str(snapshot.get("best_ask", "0")) if snapshot.get("best_ask") else None,
        "bid_qty": str(snapshot.get("bid_qty", "0")) if snapshot.get("bid_qty") else None,
        "ask_qty": str(snapshot.get("ask_qty", "0")) if snapshot.get("ask_qty") else None,
        "spread_bps": str(snapshot.get("spread_bps", "0")) if snapshot.get("spread_bps") else None,
        "volume_24h": str(snapshot.get("volume_24h", "0")) if snapshot.get("volume_24h") else None,
        "is_stale": snapshot.get("is_stale", False),
    }


@router.post("/snapshot/{symbol}/refresh")
async def refresh_snapshot(
    symbol: str,
    user: CurrentUser,
    db: DBSession,
) -> dict:
    """Tạo một ảnh chụp nhanh thị trường mới từ Binance (kích hoạt thủ công)."""
    service = _get_market_service(db)
    snapshot = await service.build_and_save_snapshot(symbol)
    return {
        "status": "ok",
        "symbol": symbol,
        "price": str(snapshot["last_price"]),
        "spread_bps": str(snapshot["spread_bps"]),
        "quality": snapshot.get("data_quality", "GOOD"),
    }


# ── Chất lượng dữ liệu ─────────────────────────────────────────────────


@router.get("/quality/{symbol}")
async def check_data_quality(
    symbol: str,
    user: CurrentUser,
    db: DBSession,
    timeframe: str = Query(default="15m"),
) -> dict:
    """Kiểm tra chất lượng dữ liệu cho một cặp giao dịch/khung thời gian."""
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
    """Điền (backfill) dữ liệu nến bị thiếu từ Binance REST API."""
    service = _get_market_service(db)
    return await service.backfill_gaps(symbol, timeframe, hours_back)


# ── Thông tin sàn (Exchange Info) ────────────────────────────────────────────────


@router.get("/exchange-info/{symbol}", response_model=SymbolInfo)
async def get_exchange_info(
    symbol: str,
    user: CurrentUser,
) -> SymbolInfo:
    """Lấy quy tắc giao dịch của một cặp tiền từ Binance."""
    info = await binance_client.get_exchange_info(symbol)
    return SymbolInfo(**info)
