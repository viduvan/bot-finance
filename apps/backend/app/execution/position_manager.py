"""Paper Position Manager — tracks open and closed paper positions.

Handles:
- Opening positions (LONG/SHORT)
- Computing unrealized PnL at any price
- Closing positions and computing realized net PnL
- Computing return percentage and holding time
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

import structlog

logger = structlog.get_logger(__name__)


class PaperPositionManager:
    """Manages paper trading positions with P&L computation.

    All values are Decimal for precision.
    Positions are tracked as plain dicts for simplicity
    (persist to DB via the execution service).
    """

    def open_position(
        self,
        symbol: str,
        side: str,
        entry_price: Decimal,
        quantity: Decimal,
        fee: Decimal,
        environment: str = "PAPER",
    ) -> dict[str, Any]:
        """Create and return a new open position.

        Args:
            symbol: Trading pair e.g. 'BTCUSDT'
            side: 'LONG' or 'SHORT'
            entry_price: Fill price for the opening order
            quantity: Position size
            fee: Entry fee paid
            environment: 'PAPER' or 'LIVE'

        Returns:
            Position dict with all fields
        """
        now = datetime.now(UTC)
        position = {
            "id": str(uuid4()),
            "symbol": symbol,
            "side": side,
            "entry_price": entry_price,
            "quantity": quantity,
            "current_price": entry_price,
            "unrealized_pnl": Decimal("0"),
            "total_fee": fee,
            "environment": environment,
            "status": "OPEN",
            "opened_at": now,
            "closed_at": None,
        }

        logger.info(
            "paper_position_opened",
            symbol=symbol,
            side=side,
            entry_price=str(entry_price),
            quantity=str(quantity),
        )
        return position

    def calc_unrealized_pnl(
        self,
        position: dict[str, Any],
        current_price: Decimal,
    ) -> Decimal:
        """Compute unrealized PnL at a given market price.

        LONG:  (current - entry) × qty
        SHORT: (entry - current) × qty
        """
        entry = position["entry_price"]
        qty = position["quantity"]
        side = position["side"]

        if side == "LONG":
            return (current_price - entry) * qty
        else:  # SHORT
            return (entry - current_price) * qty

    def close_position(
        self,
        position: dict[str, Any],
        exit_price: Decimal,
        fee: Decimal,
        close_reason: str = "MANUAL",
    ) -> dict[str, Any]:
        """Close a position and compute realized P&L.

        Args:
            position: Open position dict
            exit_price: Fill price for the closing order
            fee: Exit fee paid
            close_reason: Why it was closed (TAKE_PROFIT, STOP_LOSS, MANUAL, etc.)

        Returns:
            TradeResult dict with gross_pnl, net_pnl, return_percent, etc.
        """
        now = datetime.now(UTC)
        side = position["side"]
        entry = position["entry_price"]
        qty = position["quantity"]
        entry_fee = position["total_fee"]

        # Gross PnL (before fees)
        if side == "LONG":
            gross_pnl = (exit_price - entry) * qty
        else:  # SHORT
            gross_pnl = (entry - exit_price) * qty

        total_fee = entry_fee + fee
        net_pnl = gross_pnl - total_fee

        # Return % relative to notional (entry × qty)
        notional = entry * qty
        return_pct = (net_pnl / notional * 100) if notional > 0 else Decimal("0")

        # Holding time
        opened_at = position["opened_at"]
        if isinstance(opened_at, datetime):
            holding_seconds = int((now - opened_at).total_seconds())
        else:
            holding_seconds = 0

        trade_result = {
            "position_id": position["id"],
            "symbol": position["symbol"],
            "side": side,
            "entry_price": entry,
            "exit_price": exit_price,
            "quantity": qty,
            "gross_pnl": gross_pnl.quantize(Decimal("0.00000001")),
            "total_fee": total_fee.quantize(Decimal("0.00000001")),
            "net_pnl": net_pnl.quantize(Decimal("0.00000001")),
            "return_percent": return_pct.quantize(Decimal("0.0001")),
            "holding_time_seconds": holding_seconds,
            "close_reason": close_reason,
            "environment": position["environment"],
            "closed_at": now,
        }

        # Update position dict to reflect closure
        position["status"] = "CLOSED"
        position["closed_at"] = now
        position["current_price"] = exit_price
        position["unrealized_pnl"] = Decimal("0")

        logger.info(
            "paper_position_closed",
            symbol=position["symbol"],
            side=side,
            gross_pnl=str(gross_pnl),
            net_pnl=str(net_pnl),
            close_reason=close_reason,
        )

        return trade_result
