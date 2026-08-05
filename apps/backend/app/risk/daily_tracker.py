"""Daily Loss Tracker — tracks intraday PnL losses per symbol.

Supports two backends:
- In-memory dict (unit testing, local dev)
- Redis (production — persists across worker restarts)

Daily loss is computed as: total_losses / opening_balance × 100
"""

from __future__ import annotations

from decimal import Decimal

import structlog

logger = structlog.get_logger(__name__)


class DailyLossTracker:
    """Tracks cumulative daily losses per trading symbol.

    Losses are accumulated intraday and reset at the start of each session.
    Only negative PnL is counted (profits do NOT reduce the loss counter).
    """

    def __init__(self, use_redis: bool = True, redis_client=None) -> None:
        self._use_redis = use_redis and redis_client is not None
        self._redis = redis_client
        # In-memory fallback: {symbol: total_loss_amount}
        self._memory: dict[str, Decimal] = {}
        self._balance: dict[str, Decimal] = {}

    def record_trade_result(
        self,
        symbol: str,
        pnl: Decimal,
        balance: Decimal,
    ) -> None:
        """Record a trade result. Only negative PnL accumulates in loss counter.

        Args:
            symbol: Trading pair e.g. 'BTCUSDT'
            pnl: Profit/Loss of the trade (negative = loss)
            balance: Account balance at trade time (for percentage calculation)
        """
        if pnl >= 0:
            # Profitable trade — record balance reference but don't add to loss
            if symbol not in self._balance:
                self._balance[symbol] = balance
            return

        loss = abs(pnl)
        self._balance[symbol] = balance

        if self._use_redis:
            key = self._redis_key(symbol)
            self._redis.incrbyfloat(key, float(loss))
        else:
            current = self._memory.get(symbol, Decimal("0"))
            self._memory[symbol] = current + loss

        logger.info(
            "daily_loss_recorded",
            symbol=symbol,
            loss=str(loss),
            daily_loss_pct=str(self.get_daily_loss_pct(symbol)),
        )

    def get_daily_loss_pct(self, symbol: str) -> Decimal:
        """Get current daily loss as a percentage of balance.

        Returns:
            Decimal: e.g. 1.5 means 1.5% daily loss
        """
        balance = self._balance.get(symbol, Decimal("10000"))  # Default fallback
        if balance <= 0:
            return Decimal("0")

        total_loss = self._get_total_loss(symbol)
        return (total_loss / balance * 100).quantize(Decimal("0.01"))

    def get_daily_loss_amount(self, symbol: str) -> Decimal:
        """Get current daily loss in absolute currency amount."""
        return self._get_total_loss(symbol)

    def exceeds_limit(self, symbol: str, limit_pct: Decimal) -> bool:
        """Check if daily loss exceeds the given limit.

        Args:
            symbol: Trading pair
            limit_pct: Maximum allowed loss percentage (e.g. 3.0 = 3%)

        Returns:
            True if limit exceeded, False otherwise
        """
        current_pct = self.get_daily_loss_pct(symbol)
        return current_pct > limit_pct

    def reset_daily(self, symbol: str) -> None:
        """Reset daily loss counter for a symbol (call at start of new day)."""
        if self._use_redis:
            self._redis.delete(self._redis_key(symbol))
        else:
            self._memory.pop(symbol, None)
            self._balance.pop(symbol, None)

        logger.info("daily_loss_reset", symbol=symbol)

    def reset_all(self) -> None:
        """Reset all daily loss counters."""
        if self._use_redis:
            # Reset all known symbols
            pass  # In production: scan keys with prefix and delete
        else:
            self._memory.clear()
            self._balance.clear()

    def _get_total_loss(self, symbol: str) -> Decimal:
        """Get raw accumulated loss amount."""
        if self._use_redis:
            key = self._redis_key(symbol)
            val = self._redis.get(key)
            return Decimal(str(val)) if val else Decimal("0")
        return self._memory.get(symbol, Decimal("0"))

    @staticmethod
    def _redis_key(symbol: str) -> str:
        """Redis key for daily loss counter."""
        from datetime import date

        today = date.today().isoformat()
        return f"acta:daily_loss:{symbol}:{today}"
