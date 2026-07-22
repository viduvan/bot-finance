"""Paper PnL Tracker — aggregates realized and unrealized P&L.

Tracks:
- Total realized P&L from closed trades
- Current unrealized P&L from open positions
- Win/loss counts, win rate
- Profit factor, max drawdown
- Running equity curve

In-memory for unit tests; Redis-backed for production persistence.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class PaperPnLTracker:
    """Aggregates all P&L metrics for paper trading performance.

    Usage:
        tracker = PaperPnLTracker()
        tracker.record_trade(net_pnl=Decimal("100"), symbol="BTCUSDT")
        tracker.update_unrealized(Decimal("25"))
        summary = tracker.get_summary()
    """

    def __init__(self) -> None:
        self._realized_pnl = Decimal("0")
        self._unrealized_pnl = Decimal("0")
        self._total_trades = 0
        self._winning_trades = 0
        self._losing_trades = 0
        self._gross_wins = Decimal("0")
        self._gross_losses = Decimal("0")

        # For max drawdown: track running equity
        self._equity_curve: list[Decimal] = [Decimal("0")]
        self._peak_equity = Decimal("0")
        self._max_drawdown = Decimal("0")

        # Symbol breakdown
        self._by_symbol: dict[str, dict] = {}

    def record_trade(self, net_pnl: Decimal, symbol: str) -> None:
        """Record a completed trade result.

        Args:
            net_pnl: Net realized P&L (after fees) — can be negative
            symbol: Trading pair
        """
        self._realized_pnl += net_pnl
        self._total_trades += 1

        if net_pnl > 0:
            self._winning_trades += 1
            self._gross_wins += net_pnl
        elif net_pnl < 0:
            self._losing_trades += 1
            self._gross_losses += abs(net_pnl)

        # Update equity curve and drawdown
        current_equity = self._realized_pnl
        self._equity_curve.append(current_equity)

        if current_equity > self._peak_equity:
            self._peak_equity = current_equity

        drawdown = self._peak_equity - current_equity
        if drawdown > self._max_drawdown:
            self._max_drawdown = drawdown

        # Per-symbol tracking
        if symbol not in self._by_symbol:
            self._by_symbol[symbol] = {
                "realized_pnl": Decimal("0"),
                "trades": 0,
                "wins": 0,
            }
        self._by_symbol[symbol]["realized_pnl"] += net_pnl
        self._by_symbol[symbol]["trades"] += 1
        if net_pnl > 0:
            self._by_symbol[symbol]["wins"] += 1

        logger.debug(
            "pnl_recorded",
            net_pnl=str(net_pnl),
            total_realized=str(self._realized_pnl),
            wins=self._winning_trades,
            losses=self._losing_trades,
        )

    def update_unrealized(self, unrealized_pnl: Decimal) -> None:
        """Update the current unrealized P&L from open positions."""
        self._unrealized_pnl = unrealized_pnl

    def get_summary(self) -> dict[str, Any]:
        """Compute and return the full P&L summary."""
        win_rate = Decimal("0")
        if self._total_trades > 0:
            win_rate = (
                Decimal(str(self._winning_trades)) / Decimal(str(self._total_trades)) * 100
            ).quantize(Decimal("0.01"))

        profit_factor = Decimal("0")
        if self._gross_losses > 0:
            profit_factor = (self._gross_wins / self._gross_losses).quantize(Decimal("0.01"))
        elif self._gross_wins > 0:
            profit_factor = Decimal("999.99")  # No losses → technically infinite

        return {
            "realized_pnl": self._realized_pnl,
            "unrealized_pnl": self._unrealized_pnl,
            "total_pnl": self._realized_pnl + self._unrealized_pnl,
            "total_trades": self._total_trades,
            "winning_trades": self._winning_trades,
            "losing_trades": self._losing_trades,
            "win_rate": win_rate,
            "gross_wins": self._gross_wins,
            "gross_losses": self._gross_losses,
            "profit_factor": profit_factor,
            "max_drawdown": self._max_drawdown,
            "by_symbol": {
                sym: {
                    "realized_pnl": str(data["realized_pnl"]),
                    "trades": data["trades"],
                    "wins": data["wins"],
                }
                for sym, data in self._by_symbol.items()
            },
        }
