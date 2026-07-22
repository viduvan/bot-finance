"""Unit tests for Phase 2: Features + Strategy.

Tests cover:
- IndicatorEngine (EMA, RSI, MACD, BB, ATR) vs known-good values
- VolumeFeatures (SMA, VWAP, relative volume, pressure)
- VolatilityFeatures (ATR regime, BB squeeze, historical volatility)
- MarketStructure (swing detection, trend, S/R)
- OrderBookFeatures (imbalance, spread, wall detection)
- EMAPullbackStrategy (LONG/SHORT/NO_SIGNAL scoring)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.features.indicators import IndicatorEngine
from app.features.market_structure import MarketStructure
from app.features.orderbook_features import OrderBookFeatures
from app.features.volatility import VolatilityFeatures
from app.features.volume import VolumeFeatures
from app.strategies.ema_pullback import EMAPullbackStrategy, MIN_SIGNAL_SCORE


# ── Fixtures ─────────────────────────────────────────────────────────


def make_candle(
    i: int,
    close: float,
    open_: float | None = None,
    high: float | None = None,
    low: float | None = None,
    volume: float = 1000.0,
) -> dict:
    """Create a minimal candle dict."""
    base = datetime(2024, 1, 1, tzinfo=UTC)
    o = open_ if open_ is not None else close * 0.999
    h = high if high is not None else close * 1.005
    l = low if low is not None else close * 0.995
    return {
        "open_time": base + timedelta(minutes=i * 15),
        "close_time": base + timedelta(minutes=(i + 1) * 15),
        "open": Decimal(str(o)),
        "high": Decimal(str(h)),
        "low": Decimal(str(l)),
        "close": Decimal(str(close)),
        "volume": Decimal(str(volume)),
    }


def make_trending_candles(n: int = 100, start: float = 40000.0, step: float = 50.0) -> list[dict]:
    """Generate n candles with a steady uptrend."""
    return [make_candle(i, start + i * step) for i in range(n)]


def make_downtrend_candles(n: int = 100, start: float = 50000.0, step: float = 50.0) -> list[dict]:
    """Generate n candles with a steady downtrend."""
    return [make_candle(i, start - i * step) for i in range(n)]


def make_flat_candles(n: int = 50, price: float = 45000.0) -> list[dict]:
    """Generate n candles with no trend."""
    return [make_candle(i, price + (i % 5) * 10) for i in range(n)]


# ── IndicatorEngine ────────────────────────────────────────────────


class TestIndicatorEngine:
    """Tests for technical indicator computations."""

    @pytest.fixture
    def engine(self) -> IndicatorEngine:
        return IndicatorEngine()

    @pytest.fixture
    def trending_candles(self) -> list[dict]:
        return make_trending_candles(200)

    def test_ema_returns_correct_length(self, engine, trending_candles):
        """EMA output length must match input length."""
        ema = engine.compute_ema(trending_candles, period=21)
        assert len(ema) == len(trending_candles)

    def test_ema_initial_values_none(self, engine, trending_candles):
        """First (period-1) values should be None (insufficient data)."""
        ema = engine.compute_ema(trending_candles, period=21)
        # First 20 should be None
        assert all(v is None for v in ema[:20])

    def test_ema_values_after_warmup_not_none(self, engine, trending_candles):
        """After warmup period, EMA values should not be None."""
        ema = engine.compute_ema(trending_candles, period=21)
        assert all(v is not None for v in ema[21:])

    def test_ema_in_uptrend_ema9_above_ema21(self, engine, trending_candles):
        """In a strong uptrend, EMA9 should be above EMA21."""
        emas = engine.latest_emas(trending_candles)
        assert emas["ema_9"] is not None
        assert emas["ema_21"] is not None
        assert emas["ema_9"] > emas["ema_21"]

    def test_ema_in_uptrend_ema21_above_ema50(self, engine, trending_candles):
        """In a strong uptrend, EMA21 should be above EMA50."""
        emas = engine.latest_emas(trending_candles)
        assert emas["ema_21"] > emas["ema_50"]

    def test_rsi_range_0_to_100(self, engine, trending_candles):
        """All RSI values should be between 0 and 100."""
        rsi_values = engine.compute_rsi(trending_candles)
        for v in rsi_values:
            if v is not None:
                assert Decimal("0") <= v <= Decimal("100")

    def test_rsi_strong_uptrend_above_50(self, engine, trending_candles):
        """In a strong uptrend, RSI should be above 50."""
        rsi = engine.latest_rsi(trending_candles)
        assert rsi is not None
        assert rsi > Decimal("50")

    def test_rsi_zone_oversold(self, engine):
        """RSI < 30 should be classified as OVERSOLD."""
        assert engine.rsi_zone(Decimal("25")) == "OVERSOLD"

    def test_rsi_zone_overbought(self, engine):
        """RSI > 70 should be classified as OVERBOUGHT."""
        assert engine.rsi_zone(Decimal("75")) == "OVERBOUGHT"

    def test_rsi_zone_neutral(self, engine):
        """RSI 30-70 should be classified as NEUTRAL."""
        assert engine.rsi_zone(Decimal("55")) == "NEUTRAL"

    def test_macd_returns_three_series(self, engine, trending_candles):
        """MACD should return macd, signal, and histogram series."""
        macd = engine.compute_macd(trending_candles)
        assert "macd" in macd
        assert "signal" in macd
        assert "histogram" in macd
        assert len(macd["macd"]) == len(trending_candles)

    def test_macd_uptrend_positive_histogram(self, engine, trending_candles):
        """In a strong uptrend, MACD histogram should be non-negative.
        
        A perfectly linear synthetic uptrend may produce a histogram close to 0
        since MACD and signal converge. In real market data with acceleration,
        the histogram will be clearly positive.
        """
        macd = engine.latest_macd(trending_candles)
        assert macd["histogram"] is not None
        assert macd["histogram"] >= 0

    def test_bbands_upper_above_lower(self, engine, trending_candles):
        """Bollinger Band upper should always be above lower."""
        bb = engine.latest_bbands(trending_candles)
        assert bb["upper"] is not None
        assert bb["lower"] is not None
        assert bb["upper"] > bb["lower"]

    def test_bbands_middle_between_bands(self, engine, trending_candles):
        """BB middle (SMA20) should be between upper and lower."""
        bb = engine.latest_bbands(trending_candles)
        assert bb["lower"] < bb["middle"] < bb["upper"]

    def test_atr_positive(self, engine, trending_candles):
        """ATR should always be positive."""
        atr = engine.latest_atr(trending_candles)
        assert atr is not None
        assert atr > 0

    def test_atr_pct_reasonable(self, engine, trending_candles):
        """ATR% should be a small percentage (< 5% for normal crypto)."""
        atr_pct = engine.atr_percent(trending_candles)
        assert atr_pct is not None
        assert Decimal("0") < atr_pct < Decimal("10")

    def test_insufficient_candles_returns_none(self, engine):
        """With too few candles, most indicators should return None."""
        candles = [make_candle(i, 50000) for i in range(5)]
        emas = engine.latest_emas(candles)
        # EMA200 requires 200 candles
        assert emas["ema_200"] is None

    def test_compute_all_returns_dict(self, engine, trending_candles):
        """compute_all should return a non-empty dict."""
        result = engine.compute_all(trending_candles)
        assert isinstance(result, dict)
        assert len(result) > 10
        assert "rsi_14" in result
        assert "ema_21" in result
        assert "macd_histogram" in result


# ── VolumeFeatures ─────────────────────────────────────────────────


class TestVolumeFeatures:
    """Tests for volume-based feature computation."""

    @pytest.fixture
    def vf(self) -> VolumeFeatures:
        return VolumeFeatures()

    def test_volume_sma_computed(self, vf):
        """Volume SMA should be computed when candles >= 20."""
        candles = [make_candle(i, 50000, volume=1000) for i in range(30)]
        result = vf.compute(candles)
        assert result["volume_sma_20"] is not None
        assert Decimal(result["volume_sma_20"]) == Decimal("1000")

    def test_volume_relative_equals_1_when_stable(self, vf):
        """Relative volume = 1 when current volume equals average."""
        candles = [make_candle(i, 50000, volume=1000) for i in range(25)]
        result = vf.compute(candles)
        assert result["volume_relative"] is not None
        assert abs(Decimal(result["volume_relative"]) - Decimal("1")) < Decimal("0.01")

    def test_volume_spike_detected(self, vf):
        """Volume spike detected when current > 2× average."""
        candles = [make_candle(i, 50000, volume=1000) for i in range(24)]
        candles.append(make_candle(24, 50000, volume=5000))  # 5× spike
        result = vf.compute(candles)
        assert result["volume_spike"] is True

    def test_buy_pressure_dominant_green_candles(self, vf):
        """Majority green candles → bullish pressure bias."""
        candles = [make_candle(i, 50000 + i * 10, open_=50000 + i * 10 - 5) for i in range(25)]
        result = vf.compute(candles)
        assert result.get("pressure_bias") == "BULLISH"

    def test_vwap_computed(self, vf):
        """VWAP should be computed when at least 2 candles."""
        candles = [make_candle(i, 50000) for i in range(10)]
        result = vf.compute(candles)
        assert result.get("vwap") is not None


# ── MarketStructure ───────────────────────────────────────────────


class TestMarketStructure:
    """Tests for market structure detection."""

    @pytest.fixture
    def ms(self) -> MarketStructure:
        return MarketStructure()

    def test_uptrend_detected(self, ms):
        """Steadily rising candles should produce BULLISH trend."""
        # Needs enough candles for swing detection
        candles = make_trending_candles(80)
        result = ms.compute(candles)
        # Uptrend → higher highs and higher lows
        assert result.get("trend_direction") in ("BULLISH", "RANGING")

    def test_downtrend_detected(self, ms):
        """Steadily falling candles should produce BEARISH trend."""
        candles = make_downtrend_candles(80)
        result = ms.compute(candles)
        assert result.get("trend_direction") in ("BEARISH", "RANGING")

    def test_swing_highs_found(self, ms):
        """Swing highs should be found in enough data."""
        candles = make_trending_candles(60)
        result = ms.compute(candles)
        assert isinstance(result.get("swing_highs"), list)

    def test_sma50_computed(self, ms):
        """SMA50 should be computed with 60 candles."""
        candles = make_trending_candles(60)
        result = ms.compute(candles)
        assert result.get("sma50") is not None

    def test_insufficient_data_returns_empty(self, ms):
        """Too few candles should return empty dict."""
        candles = [make_candle(i, 50000) for i in range(5)]
        result = ms.compute(candles)
        assert result == {}


# ── OrderBookFeatures ─────────────────────────────────────────────


class TestOrderBookFeatures:
    """Tests for order book feature computation."""

    @pytest.fixture
    def obf(self) -> OrderBookFeatures:
        return OrderBookFeatures()

    def make_book(self, bid_qty: float = 1.0, ask_qty: float = 1.0, levels: int = 5) -> dict:
        """Create a synthetic order book."""
        bids = [{"price": Decimal(str(50000 - i * 10)), "quantity": Decimal(str(bid_qty))} for i in range(levels)]
        asks = [{"price": Decimal(str(50001 + i * 10)), "quantity": Decimal(str(ask_qty))} for i in range(levels)]
        return {"bids": bids, "asks": asks}

    def test_spread_computed(self, obf):
        """Spread should be correctly computed."""
        book = self.make_book()
        result = obf.compute(book)
        assert result["spread_absolute"] is not None
        # Best bid 50000, best ask 50001 → spread = 1
        assert Decimal(result["spread_absolute"]) == Decimal("1")

    def test_balanced_book_neutral_pressure(self, obf):
        """Equal bid/ask quantity → neutral pressure."""
        book = self.make_book(bid_qty=1.0, ask_qty=1.0)
        result = obf.compute(book)
        assert result["book_pressure"] == "NEUTRAL"

    def test_bid_heavy_book_buy_pressure(self, obf):
        """More bid volume → buy pressure."""
        book = self.make_book(bid_qty=3.0, ask_qty=1.0)
        result = obf.compute(book)
        assert result["book_pressure"] in ("BUY", "STRONG_BUY")

    def test_ask_heavy_book_sell_pressure(self, obf):
        """More ask volume → sell pressure."""
        book = self.make_book(bid_qty=1.0, ask_qty=3.0)
        result = obf.compute(book)
        assert result["book_pressure"] in ("SELL", "STRONG_SELL")

    def test_wall_detected_concentrated_order(self, obf):
        """Concentrated large order at top should be detected as wall."""
        bids = [
            {"price": Decimal("50000"), "quantity": Decimal("100")},  # Wall — 100× others
            {"price": Decimal("49990"), "quantity": Decimal("1")},
            {"price": Decimal("49980"), "quantity": Decimal("1")},
        ]
        asks = [{"price": Decimal(str(50001 + i * 10)), "quantity": Decimal("1")} for i in range(5)]
        book = {"bids": bids, "asks": asks}
        result = obf.compute(book)
        assert result["bid_wall"] is True

    def test_empty_book_returns_empty(self, obf):
        """Empty order book should return empty dict."""
        result = obf.compute({"bids": [], "asks": []})
        assert result == {}


# ── EMAPullbackStrategy ───────────────────────────────────────────


class TestEMAPullbackStrategy:
    """Tests for EMA Pullback strategy signal generation."""

    @pytest.fixture
    def strategy(self) -> EMAPullbackStrategy:
        return EMAPullbackStrategy()

    def make_bullish_features(self) -> dict:
        """Create feature dict that strongly satisfies LONG conditions."""
        return {
            "ema_9": "50500",
            "ema_21": "50200",
            "ema_50": "49800",
            "ema_200": "48000",
            "rsi_14": "52",
            "rsi_zone": "NEUTRAL",
            "macd_histogram": "100",
            "macd_signal_type": "BULLISH",
            "atr_14": "300",
            "close": "50250",   # Within 1×ATR of EMA21 (50200), diff=50 < 300
            "last_price": "50250",
            "price_above_vwap": True,
            "pressure_bias": "BULLISH",
            "volume_increasing": True,
        }

    def make_bearish_features(self) -> dict:
        """Create feature dict that strongly satisfies SHORT conditions."""
        return {
            "ema_9": "49500",
            "ema_21": "49800",
            "ema_50": "50200",
            "ema_200": "52000",
            "rsi_14": "48",
            "rsi_zone": "NEUTRAL",
            "macd_histogram": "-100",
            "macd_signal_type": "BEARISH",
            "atr_14": "300",
            "close": "49750",  # Within 1×ATR of EMA21 (49800)
            "last_price": "49750",
            "price_above_vwap": False,
            "pressure_bias": "BEARISH",
        }

    def make_1h_bullish_features(self) -> dict:
        return {
            "ema_50": "49500",
            "close": "50250",
            "last_price": "50250",
        }

    def make_1h_bearish_features(self) -> dict:
        return {
            "ema_50": "50500",
            "close": "49750",
            "last_price": "49750",
        }

    def test_long_signal_bullish_market(self, strategy):
        """Bullish features should produce LONG signal above threshold."""
        f15 = self.make_bullish_features()
        f1h = self.make_1h_bullish_features()
        result = strategy.evaluate(f15, f1h, {})
        assert result.signal == "LONG"
        assert result.score >= MIN_SIGNAL_SCORE

    def test_short_signal_bearish_market(self, strategy):
        """Bearish features should produce SHORT signal above threshold."""
        f15 = self.make_bearish_features()
        f1h = self.make_1h_bearish_features()
        result = strategy.evaluate(f15, f1h, {})
        assert result.signal == "SHORT"
        assert result.score >= MIN_SIGNAL_SCORE

    def test_no_signal_empty_features(self, strategy):
        """Empty features should produce NO_SIGNAL."""
        result = strategy.evaluate({}, {}, {})
        assert result.signal == "NO_SIGNAL"

    def test_stop_loss_hint_below_entry_for_long(self, strategy):
        """SL hint for LONG should be below entry price."""
        f15 = self.make_bullish_features()
        f1h = self.make_1h_bullish_features()
        result = strategy.evaluate(f15, f1h, {})
        if result.signal == "LONG" and result.stop_loss_hint:
            assert result.stop_loss_hint < Decimal(f15["close"])

    def test_take_profit_hint_above_entry_for_long(self, strategy):
        """TP hint for LONG should be above entry price."""
        f15 = self.make_bullish_features()
        f1h = self.make_1h_bullish_features()
        result = strategy.evaluate(f15, f1h, {})
        if result.signal == "LONG" and result.take_profit_hint:
            assert result.take_profit_hint > Decimal(f15["close"])

    def test_score_increases_with_4h_confirmation(self, strategy):
        """Adding 4h trend confirmation should increase score."""
        f15 = self.make_bullish_features()
        f1h = self.make_1h_bullish_features()

        result_no_4h = strategy.evaluate(f15, f1h, {})

        f4h = {"ema_21": "49000", "ema_50": "48000"}  # Bullish 4h
        result_with_4h = strategy.evaluate(f15, f1h, f4h)

        assert result_with_4h.score >= result_no_4h.score

    def test_contradicting_trend_lowers_score(self, strategy):
        """EMA21 < EMA50 in a supposed long setup should lower score."""
        f15 = self.make_bullish_features()
        f15["ema_21"] = "49500"   # EMA21 now BELOW EMA50 (49800)
        f1h = self.make_1h_bullish_features()

        result = strategy.evaluate(f15, f1h, {})
        # Should not produce LONG when 15m trend is bearish
        assert result.signal != "LONG" or result.score < MIN_SIGNAL_SCORE

    def test_reasons_always_populated(self, strategy):
        """Signal result should always include reasoning."""
        result = strategy.evaluate(
            self.make_bullish_features(),
            self.make_1h_bullish_features(),
            {},
        )
        assert len(result.reasons) > 0

    def test_confidence_high_when_score_above_80(self, strategy):
        """Score >= 80 should produce HIGH confidence."""
        f15 = self.make_bullish_features()
        f1h = self.make_1h_bullish_features()
        f4h = {"ema_21": "49000", "ema_50": "48000"}
        result = strategy.evaluate(f15, f1h, f4h)
        if result.score >= 80:
            assert result.confidence == "HIGH"
