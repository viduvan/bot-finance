"""Data validation service.

Detects gaps, stale data, and anomalies in market data.
Ensures data quality before feeding into the analysis pipeline.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import structlog

from app.core.constants import MAX_DATA_STALENESS_SECONDS

logger = structlog.get_logger(__name__)

# Timeframe → expected interval in seconds
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

# Maximum allowed price change per candle (as multiplier)
# e.g. 50% means close can be at most 1.5x or 0.5x of open
MAX_CANDLE_PRICE_CHANGE_PCT = Decimal("50.0")

# Maximum allowed volume spike (compared to 20-candle average)
MAX_VOLUME_SPIKE_MULTIPLIER = 50


class DataValidator:
    """Validates market data for quality issues."""

    def validate_candles(
        self,
        candles: list[dict],
        symbol: str,
        timeframe: str,
    ) -> dict:
        """Validate a list of candles and return quality report.

        Returns:
            dict with keys: is_healthy, total, gaps, anomalies, warnings
        """
        if not candles:
            return {
                "is_healthy": False,
                "total": 0,
                "gaps": [],
                "anomalies": [],
                "warnings": ["No candle data"],
            }

        interval_seconds = TIMEFRAME_INTERVALS.get(timeframe)
        if not interval_seconds:
            return {
                "is_healthy": True,
                "total": len(candles),
                "gaps": [],
                "anomalies": [],
                "warnings": [f"Unknown timeframe: {timeframe}"],
            }

        # Sort by open_time ascending
        sorted_candles = sorted(candles, key=lambda c: c["open_time"])

        gaps = []
        anomalies = []
        warnings = []

        # Check for gaps
        for i in range(1, len(sorted_candles)):
            prev = sorted_candles[i - 1]
            curr = sorted_candles[i]

            prev_time = prev["open_time"]
            curr_time = curr["open_time"]

            # Allow 10% tolerance on interval
            expected_diff = timedelta(seconds=interval_seconds)
            actual_diff = curr_time - prev_time

            if actual_diff > expected_diff * 1.5:
                missing_count = int(actual_diff.total_seconds() / interval_seconds) - 1
                gaps.append({
                    "start": prev_time.isoformat(),
                    "end": curr_time.isoformat(),
                    "missing_candles": missing_count,
                })

        # Check for price anomalies
        for c in sorted_candles:
            o, h, l, cl = c["open"], c["high"], c["low"], c["close"]

            # OHLC integrity: high >= max(open, close), low <= min(open, close)
            if h < o or h < cl:
                anomalies.append({
                    "time": c["open_time"].isoformat(),
                    "type": "high_below_open_or_close",
                    "values": {"open": str(o), "high": str(h), "close": str(cl)},
                })

            if l > o or l > cl:
                anomalies.append({
                    "time": c["open_time"].isoformat(),
                    "type": "low_above_open_or_close",
                    "values": {"open": str(o), "low": str(l), "close": str(cl)},
                })

            # Extreme price change
            if o > 0:
                change_pct = abs((cl - o) / o * 100)
                if change_pct > MAX_CANDLE_PRICE_CHANGE_PCT:
                    anomalies.append({
                        "time": c["open_time"].isoformat(),
                        "type": "extreme_price_change",
                        "change_pct": str(change_pct),
                    })

            # Zero volume (not necessarily an error, but suspicious)
            if c["volume"] == 0:
                warnings.append(f"Zero volume at {c['open_time'].isoformat()}")

        # Volume spike detection
        if len(sorted_candles) >= 20:
            volumes = [c["volume"] for c in sorted_candles]
            avg_volume = sum(volumes[:20]) / 20
            if avg_volume > 0:
                for c in sorted_candles[20:]:
                    if c["volume"] > avg_volume * MAX_VOLUME_SPIKE_MULTIPLIER:
                        warnings.append(
                            f"Volume spike at {c['open_time'].isoformat()}: "
                            f"{c['volume']} vs avg {avg_volume:.2f}"
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
        """Check if data is stale."""
        if last_update is None:
            return {
                "is_stale": True,
                "staleness_seconds": None,
                "symbol": symbol,
                "message": "No data available",
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
        """Find time gaps that need REST backfill.

        Returns list of (start_time, end_time) tuples representing gaps.
        """
        interval_seconds = TIMEFRAME_INTERVALS.get(timeframe, 900)
        interval = timedelta(seconds=interval_seconds)

        if not candles:
            return [{"start": expected_start, "end": expected_end}]

        sorted_candles = sorted(candles, key=lambda c: c["open_time"])
        gaps = []

        # Gap at the beginning?
        first_time = sorted_candles[0]["open_time"]
        if first_time - expected_start > interval * 1.5:
            gaps.append({"start": expected_start, "end": first_time})

        # Gaps between candles
        for i in range(1, len(sorted_candles)):
            prev_time = sorted_candles[i - 1]["open_time"]
            curr_time = sorted_candles[i]["open_time"]

            if curr_time - prev_time > interval * 1.5:
                gaps.append({"start": prev_time + interval, "end": curr_time})

        # Gap at the end?
        last_time = sorted_candles[-1]["open_time"]
        if expected_end - last_time > interval * 1.5:
            gaps.append({"start": last_time + interval, "end": expected_end})

        return gaps


# Singleton instance
data_validator = DataValidator()
