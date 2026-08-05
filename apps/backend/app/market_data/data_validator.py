"""Dịch vụ kiểm tra chất lượng dữ liệu (Data validation service).

Phát hiện các khoảng trống (gaps), dữ liệu bị đóng băng/cũ (stale data), và sự bất thường trong dữ liệu thị trường.
Đảm bảo chất lượng dữ liệu trước khi đưa vào luồng phân tích (analysis pipeline).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import structlog

from app.core.constants import MAX_DATA_STALENESS_SECONDS

logger = structlog.get_logger(__name__)

# Khung thời gian → khoảng thời gian tính bằng giây
TIMEFRAME_INTERVALS: dict[str, int] = {
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "2h": 7200,
    "4h": 14400,
    "8h": 28800,
    "1d": 86400,
}

# Thay đổi giá trị tối đa cho phép trong một nến (dưới dạng hệ số nhân)
# VD: 50% nghĩa là giá đóng cửa có thể cao nhất là 1.5x hoặc thấp nhất là 0.5x so với giá mở cửa
MAX_CANDLE_PRICE_CHANGE_PCT = Decimal("50.0")

# Khối lượng đột biến tối đa cho phép (so với trung bình 20 nến gần nhất)
MAX_VOLUME_SPIKE_MULTIPLIER = 50


class DataValidator:
    """Kiểm tra dữ liệu thị trường xem có vấn đề về chất lượng không."""

    def validate_candles(
        self,
        candles: list[dict],
        symbol: str,
        timeframe: str,
    ) -> dict:
        """Kiểm tra danh sách nến và trả về báo cáo chất lượng.

        Trả về:
            dict có chứa các keys: is_healthy, total, gaps, anomalies, warnings
        """
        if not candles:
            return {
                "is_healthy": False,
                "total": 0,
                "gaps": [],
                "anomalies": [],
                "warnings": ["Không có dữ liệu nến"],
            }

        interval_seconds = TIMEFRAME_INTERVALS.get(timeframe)
        if not interval_seconds:
            return {
                "is_healthy": True,
                "total": len(candles),
                "gaps": [],
                "anomalies": [],
                "warnings": [f"Khung thời gian không xác định: {timeframe}"],
            }

        # Sắp xếp theo open_time tăng dần
        sorted_candles = sorted(candles, key=lambda c: c["open_time"])

        gaps = []
        anomalies = []
        warnings = []

        # Kiểm tra khoảng trống (gaps)
        for i in range(1, len(sorted_candles)):
            prev = sorted_candles[i - 1]
            curr = sorted_candles[i]

            prev_time = prev["open_time"]
            curr_time = curr["open_time"]

            # Cho phép sai số 10% trên khoảng thời gian
            expected_diff = timedelta(seconds=interval_seconds)
            actual_diff = curr_time - prev_time

            if actual_diff > expected_diff * 1.5:
                missing_count = int(actual_diff.total_seconds() / interval_seconds) - 1
                gaps.append(
                    {
                        "start": prev_time.isoformat(),
                        "end": curr_time.isoformat(),
                        "missing_candles": missing_count,
                    }
                )

        # Kiểm tra các bất thường về giá (price anomalies)
        for c in sorted_candles:
            o, h, l, cl = c["open"], c["high"], c["low"], c["close"]

            # Tính toàn vẹn của OHLC: high >= max(open, close), low <= min(open, close)
            if h < o or h < cl:
                anomalies.append(
                    {
                        "time": c["open_time"].isoformat(),
                        "type": "high_below_open_or_close",
                        "values": {"open": str(o), "high": str(h), "close": str(cl)},
                    }
                )

            if l > o or l > cl:
                anomalies.append(
                    {
                        "time": c["open_time"].isoformat(),
                        "type": "low_above_open_or_close",
                        "values": {"open": str(o), "low": str(l), "close": str(cl)},
                    }
                )

            # Thay đổi giá cực đoan
            if o > 0:
                change_pct = abs((cl - o) / o * 100)
                if change_pct > MAX_CANDLE_PRICE_CHANGE_PCT:
                    anomalies.append(
                        {
                            "time": c["open_time"].isoformat(),
                            "type": "extreme_price_change",
                            "change_pct": str(change_pct),
                        }
                    )

            # Khối lượng bằng 0 (chưa chắc là lỗi nhưng đáng ngờ)
            if c["volume"] == 0:
                warnings.append(f"Khối lượng bằng 0 tại {c['open_time'].isoformat()}")

        # Phát hiện đột biến khối lượng
        if len(sorted_candles) >= 20:
            volumes = [c["volume"] for c in sorted_candles]
            avg_volume = sum(volumes[:20]) / 20
            if avg_volume > 0:
                for c in sorted_candles[20:]:
                    if c["volume"] > avg_volume * MAX_VOLUME_SPIKE_MULTIPLIER:
                        warnings.append(
                            f"Đột biến khối lượng tại {c['open_time'].isoformat()}: "
                            f"{c['volume']} so với trung bình {avg_volume:.2f}"
                        )

        is_healthy = len(gaps) == 0 and len(anomalies) == 0

        return {
            "is_healthy": is_healthy,
            "total": len(sorted_candles),
            "gaps": gaps,
            "gap_count": len(gaps),
            "anomalies": anomalies,
            "warnings": warnings,
        }

    def check_staleness(self, last_update: datetime | None, symbol: str) -> dict:
        """Kiểm tra xem dữ liệu có bị cũ/đóng băng không."""
        if last_update is None:
            return {
                "is_stale": True,
                "staleness_seconds": None,
                "symbol": symbol,
                "message": "Không có dữ liệu",
            }

        now = datetime.now(UTC)
        staleness = (now - last_update).total_seconds()

        return {
            "is_stale": staleness > MAX_DATA_STALENESS_SECONDS,
            "staleness_seconds": staleness,
            "symbol": symbol,
            "last_update": last_update.isoformat(),
        }

    def find_gaps(
        self,
        candles: list[dict],
        timeframe: str,
        expected_start: datetime,
        expected_end: datetime,
    ) -> list[dict]:
        """Tìm những khoảng thời gian trống cần gọi REST API để điền đầy dữ liệu.

        Trả về danh sách chứa các tuple (start_time, end_time) đại diện cho các khoảng trống.
        """
        interval_seconds = TIMEFRAME_INTERVALS.get(timeframe, 900)
        interval = timedelta(seconds=interval_seconds)

        if not candles:
            return [{"start": expected_start, "end": expected_end}]

        sorted_candles = sorted(candles, key=lambda c: c["open_time"])
        gaps = []

        # Có khoảng trống ở đầu không?
        first_time = sorted_candles[0]["open_time"]
        if first_time - expected_start > interval * 1.5:
            gaps.append({"start": expected_start, "end": first_time})

        # Khoảng trống giữa các nến
        for i in range(1, len(sorted_candles)):
            prev_time = sorted_candles[i - 1]["open_time"]
            curr_time = sorted_candles[i]["open_time"]

            if curr_time - prev_time > interval * 1.5:
                gaps.append({"start": prev_time + interval, "end": curr_time})

        # Có khoảng trống ở cuối không?
        last_time = sorted_candles[-1]["open_time"]
        if expected_end - last_time > interval * 1.5:
            gaps.append({"start": last_time + interval, "end": expected_end})

        return gaps


# Instance dùng chung (Singleton)
data_validator = DataValidator()
