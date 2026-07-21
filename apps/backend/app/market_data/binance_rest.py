"""Binance REST API client.

Client HTTP bất đồng bộ cho Binance REST API với:
- Giới hạn tốc độ (Rate limiting: 1200 weight/phút)
- Tự động chuyển đổi giữa testnet/mainnet
- Xử lý lỗi với cơ chế thử lại (retries)
- Lưu cache thông tin sàn (exchange info)
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import settings
from app.core.exceptions import BinanceConnectionError, StaleDataError

logger = structlog.get_logger(__name__)

# Theo dõi dung lượng (weight) API Binance
_weight_used: int = 0
_weight_reset_time: datetime | None = None
_WEIGHT_LIMIT = 1200  # Mỗi phút


class BinanceRestClient:
    """Client bất đồng bộ cho Binance REST API có giới hạn tốc độ."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._exchange_info_cache: dict[str, Any] | None = None
        self._exchange_info_cached_at: datetime | None = None

    @property
    def base_url(self) -> str:
        return settings.binance_active_base_url

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            headers = {}
            if settings.binance_read_api_key:
                headers["X-MBX-APIKEY"] = settings.binance_read_api_key
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=httpx.Timeout(15.0, connect=5.0),
            )
        return self._client

    @retry(
        retry=retry_if_exception_type((httpx.ConnectError, httpx.ReadTimeout)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def _request(
        self, method: str, path: str, params: dict | None = None, weight: int = 1
    ) -> dict | list:
        """Gửi request có giới hạn tốc độ tới Binance API."""
        global _weight_used, _weight_reset_time

        # Giới hạn tốc độ đơn giản
        now = datetime.now(UTC)
        if _weight_reset_time is None or (now - _weight_reset_time).total_seconds() >= 60:
            _weight_used = 0
            _weight_reset_time = now

        if _weight_used + weight > _WEIGHT_LIMIT:
            wait_seconds = 60 - (now - _weight_reset_time).total_seconds()
            logger.warning("binance_rate_limit_approaching", weight_used=_weight_used, wait=wait_seconds)
            if wait_seconds > 0:
                await asyncio.sleep(wait_seconds)
            _weight_used = 0
            _weight_reset_time = datetime.now(UTC)

        client = await self._get_client()

        try:
            response = await client.request(method, path, params=params)

            # Theo dõi weight từ headers
            used_weight = response.headers.get("x-mbx-used-weight-1m")
            if used_weight:
                _weight_used = int(used_weight)

            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                logger.error("binance_rate_limited", retry_after=retry_after)
                await asyncio.sleep(retry_after)
                raise httpx.ReadTimeout("Bị giới hạn tốc độ (Rate limited)")

            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            logger.error("binance_api_error", status=e.response.status_code, body=e.response.text[:500])
            raise BinanceConnectionError(f"HTTP {e.response.status_code}: {e.response.text[:200]}") from e
        except httpx.ConnectError as e:
            logger.error("binance_connection_failed", error=str(e))
            raise

    # ── Dữ liệu thị trường công khai ─────────────────────────────

    async def get_klines(
        self,
        symbol: str,
        interval: str = "15m",
        limit: int = 500,
        start_time: int | None = None,
        end_time: int | None = None,
    ) -> list[dict]:
        """Lấy dữ liệu nến OHLCV.

        Trả về danh sách các dict nến với key chuẩn hóa.
        Weight: 2 nếu limit <= 100, 5 nếu <= 500, 10 nếu <= 1000.
        """
        params: dict[str, Any] = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit,
        }
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time

        weight = 2 if limit <= 100 else (5 if limit <= 500 else 10)
        raw = await self._request("GET", "/api/v3/klines", params=params, weight=weight)

        candles = []
        for k in raw:
            candles.append({
                "open_time": datetime.fromtimestamp(k[0] / 1000, tz=UTC),
                "open": Decimal(str(k[1])),
                "high": Decimal(str(k[2])),
                "low": Decimal(str(k[3])),
                "close": Decimal(str(k[4])),
                "volume": Decimal(str(k[5])),
                "close_time": datetime.fromtimestamp(k[6] / 1000, tz=UTC),
                "quote_volume": Decimal(str(k[7])),
                "trades_count": int(k[8]),
            })
        return candles

    async def get_ticker_price(self, symbol: str) -> dict:
        """Lấy giá hiện tại cho một cặp giao dịch. Weight: 2."""
        data = await self._request("GET", "/api/v3/ticker/price", params={"symbol": symbol}, weight=2)
        return {
            "symbol": data["symbol"],
            "price": Decimal(str(data["price"])),
            "timestamp": datetime.now(UTC),
        }

    async def get_ticker_24h(self, symbol: str) -> dict:
        """Lấy thống kê ticker trong 24h qua. Weight: 2."""
        data = await self._request("GET", "/api/v3/ticker/24hr", params={"symbol": symbol}, weight=2)
        return {
            "symbol": data["symbol"],
            "price": Decimal(str(data["lastPrice"])),
            "bid": Decimal(str(data["bidPrice"])),
            "ask": Decimal(str(data["askPrice"])),
            "bid_qty": Decimal(str(data["bidQty"])),
            "ask_qty": Decimal(str(data["askQty"])),
            "volume_24h": Decimal(str(data["volume"])),
            "quote_volume_24h": Decimal(str(data["quoteVolume"])),
            "price_change_24h": Decimal(str(data["priceChange"])),
            "price_change_pct_24h": Decimal(str(data["priceChangePercent"])),
            "open_price": Decimal(str(data["openPrice"])),
            "high_price": Decimal(str(data["highPrice"])),
            "low_price": Decimal(str(data["lowPrice"])),
            "trades_count": int(data["count"]),
            "timestamp": datetime.now(UTC),
        }

    async def get_book_ticker(self, symbol: str) -> dict:
        """Lấy giá bid/ask tốt nhất cho một cặp giao dịch. Weight: 2."""
        data = await self._request("GET", "/api/v3/ticker/bookTicker", params={"symbol": symbol}, weight=2)
        bid = Decimal(str(data["bidPrice"]))
        ask = Decimal(str(data["askPrice"]))
        mid = (bid + ask) / 2
        spread_bps = ((ask - bid) / mid * 10000) if mid > 0 else Decimal("0")

        return {
            "symbol": data["symbol"],
            "bid": bid,
            "ask": ask,
            "bid_qty": Decimal(str(data["bidQty"])),
            "ask_qty": Decimal(str(data["askQty"])),
            "spread_bps": spread_bps.quantize(Decimal("0.01")),
            "timestamp": datetime.now(UTC),
        }

    async def get_depth(self, symbol: str, limit: int = 20) -> dict:
        """Lấy độ sâu sổ lệnh. Weight: 5 cho limit=20, 10 cho 50, 50 cho 500."""
        weight = 5 if limit <= 20 else (10 if limit <= 50 else 50)
        data = await self._request("GET", "/api/v3/depth", params={"symbol": symbol, "limit": limit}, weight=weight)
        return {
            "symbol": symbol,
            "last_update_id": data.get("lastUpdateId"),
            "bids": [{"price": Decimal(b[0]), "quantity": Decimal(b[1])} for b in data["bids"]],
            "asks": [{"price": Decimal(a[0]), "quantity": Decimal(a[1])} for a in data["asks"]],
            "timestamp": datetime.now(UTC),
        }

    async def get_exchange_info(self, symbol: str | None = None, force_refresh: bool = False) -> dict:
        """Lấy quy tắc giao dịch của sàn. Weight: 20. Lưu cache trong 1 giờ."""
        now = datetime.now(UTC)
        if (
            not force_refresh
            and self._exchange_info_cache
            and self._exchange_info_cached_at
            and (now - self._exchange_info_cached_at).total_seconds() < 3600
        ):
            if symbol:
                for s in self._exchange_info_cache.get("symbols", []):
                    if s["symbol"] == symbol:
                        return self._parse_symbol_info(s)
            return self._exchange_info_cache

        data = await self._request("GET", "/api/v3/exchangeInfo", weight=20)
        self._exchange_info_cache = data
        self._exchange_info_cached_at = now

        if symbol:
            for s in data.get("symbols", []):
                if s["symbol"] == symbol:
                    return self._parse_symbol_info(s)
            raise BinanceConnectionError(f"Symbol {symbol} not found")

        return data

    def _parse_symbol_info(self, raw: dict) -> dict:
        """Phân tích thông tin cặp tiền từ phản hồi exchange info."""
        info: dict[str, Any] = {
            "symbol": raw["symbol"],
            "status": raw["status"],
            "base_asset": raw["baseAsset"],
            "quote_asset": raw["quoteAsset"],
            "price_precision": raw.get("pricePrecision", 8),
            "quantity_precision": raw.get("quantityPrecision", 8),
        }

        for f in raw.get("filters", []):
            if f["filterType"] == "PRICE_FILTER":
                info["tick_size"] = Decimal(f["tickSize"])
            elif f["filterType"] == "LOT_SIZE":
                info["min_quantity"] = Decimal(f["minQty"])
                info["max_quantity"] = Decimal(f["maxQty"])
                info["step_size"] = Decimal(f["stepSize"])
            elif f["filterType"] == "NOTIONAL" or f["filterType"] == "MIN_NOTIONAL":
                info["min_notional"] = Decimal(f.get("minNotional", "0"))

        return info

    async def get_server_time(self) -> datetime:
        """Lấy thời gian máy chủ Binance. Weight: 1."""
        data = await self._request("GET", "/api/v3/time", weight=1)
        return datetime.fromtimestamp(data["serverTime"] / 1000, tz=UTC)

    async def close(self) -> None:
        """Đóng kết nối HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None


# Instance dùng chung (Singleton)
binance_client = BinanceRestClient()
