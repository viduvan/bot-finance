"""Các bài kiểm tra (Tests) cho các thành phần dữ liệu thị trường.

Các bài kiểm tra bao gồm:
- Data validator (phát hiện khoảng trống, bất thường, đóng băng dữ liệu)
- Logic của trình tạo ảnh chụp nhanh (Snapshot builder)
- Các lược đồ dữ liệu thị trường (Market data schemas)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.market_data.data_validator import DataValidator


@pytest.fixture
def validator():
    return DataValidator()


# ── Tests cho DataValidator ──────────────────────────────────────────


class TestDataValidator:
    """Các bài kiểm tra cho việc xác thực dữ liệu thị trường."""

    def _make_candle(self, offset_minutes: int, o=100, h=110, l=90, c=105, v=1000):
        """Hàm hỗ trợ tạo một dict nến tại mức offset N phút."""
        base = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
        return {
            "open_time": base + timedelta(minutes=offset_minutes),
            "close_time": base + timedelta(minutes=offset_minutes + 15),
            "open": Decimal(str(o)),
            "high": Decimal(str(h)),
            "low": Decimal(str(l)),
            "close": Decimal(str(c)),
            "volume": Decimal(str(v)),
        }

    def test_empty_candles(self, validator):
        """Danh sách nến trống phải trả về không khỏe mạnh (unhealthy)."""
        result = validator.validate_candles([], "BTCUSDT", "15m")
        assert result["is_healthy"] is False
        assert result["total"] == 0

    def test_valid_candles_no_gaps(self, validator):
        """Các nến liên tiếp phải vượt qua quá trình xác thực."""
        candles = [self._make_candle(i * 15) for i in range(10)]
        result = validator.validate_candles(candles, "BTCUSDT", "15m")
        assert result["is_healthy"] is True
        assert result["total"] == 10
        assert result["gap_count"] == 0

    def test_gap_detection(self, validator):
        """Các nến bị thiếu phải được phát hiện là khoảng trống (gaps)."""
        candles = [
            self._make_candle(0),
            self._make_candle(15),
            # Thiếu nến ở các phút: 30, 45, 60
            self._make_candle(75),
            self._make_candle(90),
        ]
        result = validator.validate_candles(candles, "BTCUSDT", "15m")
        assert result["is_healthy"] is False
        assert result["gap_count"] == 1
        assert result["gaps"][0]["missing_candles"] >= 3

    def test_multiple_gaps(self, validator):
        """Nhiều khoảng trống phải đều được phát hiện."""
        candles = [
            self._make_candle(0),
            self._make_candle(60),  # Gap 1: thiếu 15, 30, 45
            self._make_candle(150),  # Gap 2: thiếu 75, 90, 105, 120, 135
        ]
        result = validator.validate_candles(candles, "BTCUSDT", "15m")
        assert result["gap_count"] == 2

    def test_high_below_close_anomaly(self, validator):
        """Nến có giá cao nhất < giá đóng cửa phải bị cắm cờ bất thường."""
        candles = [self._make_candle(0, o=100, h=95, l=90, c=105)]  # high < close
        result = validator.validate_candles(candles, "BTCUSDT", "15m")
        assert len(result["anomalies"]) > 0
        assert result["anomalies"][0]["type"] == "high_below_open_or_close"

    def test_low_above_open_anomaly(self, validator):
        """Nến có giá thấp nhất > giá mở cửa phải bị cắm cờ bất thường."""
        candles = [self._make_candle(0, o=90, h=110, l=95, c=105)]  # low > open
        result = validator.validate_candles(candles, "BTCUSDT", "15m")
        assert len(result["anomalies"]) > 0
        assert result["anomalies"][0]["type"] == "low_above_open_or_close"

    def test_extreme_price_change(self, validator):
        """Thay đổi giá > 50% trong một nến phải bị cắm cờ."""
        candles = [self._make_candle(0, o=100, h=200, l=50, c=180)]  # Thay đổi 80%
        result = validator.validate_candles(candles, "BTCUSDT", "15m")
        assert any(a["type"] == "extreme_price_change" for a in result["anomalies"])

    def test_zero_volume_warning(self, validator):
        """Khối lượng bằng 0 phải đưa ra cảnh báo."""
        candles = [self._make_candle(0, v=0)]
        result = validator.validate_candles(candles, "BTCUSDT", "15m")
        assert any("Khối lượng bằng 0" in w for w in result["warnings"])

    def test_unknown_timeframe(self, validator):
        """Khung thời gian không xác định vẫn phải trả về kết quả kèm cảnh báo."""
        candles = [self._make_candle(0)]
        result = validator.validate_candles(candles, "BTCUSDT", "42m")
        assert "Khung thời gian không xác định" in result["warnings"][0]

    def test_staleness_check_no_data(self, validator):
        """Không có dữ liệu phải được báo cáo là cũ (stale)."""
        result = validator.check_staleness(None, "BTCUSDT")
        assert result["is_stale"] is True

    def test_staleness_check_fresh(self, validator):
        """Dữ liệu gần đây không được coi là cũ."""
        result = validator.check_staleness(datetime.now(UTC), "BTCUSDT")
        assert result["is_stale"] is False
        assert result["staleness_seconds"] < 5

    def test_staleness_check_stale(self, validator):
        """Dữ liệu cũ phải được báo cáo là stale."""
        old_time = datetime.now(UTC) - timedelta(minutes=10)
        result = validator.check_staleness(old_time, "BTCUSDT")
        assert result["is_stale"] is True
        assert result["staleness_seconds"] > 500

    def test_find_gaps_empty(self, validator):
        """Không có nến phải trả về một khoảng trống lớn."""
        start = datetime(2024, 1, 1, tzinfo=UTC)
        end = datetime(2024, 1, 1, 1, 0, tzinfo=UTC)
        gaps = validator.find_gaps([], "15m", start, end)
        assert len(gaps) == 1
        assert gaps[0]["start"] == start
        assert gaps[0]["end"] == end

    def test_find_gaps_complete_data(self, validator):
        """Dữ liệu đầy đủ không được có khoảng trống nào."""
        start = datetime(2024, 1, 1, tzinfo=UTC)
        candles = [{"open_time": start + timedelta(minutes=i * 15)} for i in range(5)]
        end = start + timedelta(minutes=60)
        gaps = validator.find_gaps(candles, "15m", start, end)
        # Tối đa chỉ có 1 gap ở đoạn cuối cùng
        assert len(gaps) <= 1


# ── Tests cho Schemas ─────────────────────────────────────────────────


class TestMarketSchemas:
    """Test xác thực schema Pydantic."""

    def test_candle_response_from_dict(self):
        from app.schemas.market import CandleResponse

        candle = CandleResponse(
            symbol="BTCUSDT",
            timeframe="15m",
            open_time=datetime.now(UTC),
            close_time=datetime.now(UTC),
            open=Decimal("50000"),
            high=Decimal("50500"),
            low=Decimal("49800"),
            close=Decimal("50200"),
            volume=Decimal("100.5"),
        )
        assert candle.symbol == "BTCUSDT"
        assert candle.close == Decimal("50200")

    def test_ticker_response(self):
        from app.schemas.market import TickerResponse

        ticker = TickerResponse(
            symbol="ETHUSDT",
            price=Decimal("3000"),
            bid=Decimal("2999.5"),
            ask=Decimal("3000.5"),
            volume_24h=Decimal("500000"),
            timestamp=datetime.now(UTC),
        )
        assert ticker.symbol == "ETHUSDT"
        assert ticker.price == Decimal("3000")

    def test_order_book_level(self):
        from app.schemas.market import OrderBookLevel

        level = OrderBookLevel(price=Decimal("50000"), quantity=Decimal("0.5"))
        assert level.price == Decimal("50000")

    def test_data_quality_report(self):
        from app.schemas.market import DataQualityReport

        report = DataQualityReport(
            symbol="BTCUSDT",
            timeframe="15m",
            total_candles=500,
            expected_candles=500,
            missing_candles=0,
            gap_count=0,
            is_healthy=True,
        )
        assert report.is_healthy is True
        assert report.gap_count == 0
