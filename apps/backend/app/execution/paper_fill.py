"""Paper Fill Simulator — simulates order fills for paper trading.

Rules:
  MARKET order  → always fills immediately at current_price ± slippage
  LIMIT BUY     → fills when current_price <= order_price
  LIMIT SELL    → fills when current_price >= order_price
  Fill price    = order_price (LIMIT) or current_price ± slippage (MARKET)
  Fee           = fill_notional × fee_rate
"""

from __future__ import annotations

from decimal import ROUND_DOWN, Decimal
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

DEFAULT_FEE_RATE = Decimal("0.001")       # Binance 0.1%
DEFAULT_SLIPPAGE_BPS = Decimal("5")       # 5 basis points
PRICE_PRECISION = Decimal("0.00000001")


class PaperFillSimulator:
    """Simulates exchange order fills for paper trading environment."""

    def simulate_fill(
        self,
        order_type: str,
        order_price: Decimal | None,
        current_price: Decimal,
        quantity: Decimal,
        side: str = "BUY",
        fee_rate: Decimal = DEFAULT_FEE_RATE,
        slippage_bps: Decimal = DEFAULT_SLIPPAGE_BPS,
    ) -> dict[str, Any]:
        """Simulate an order fill attempt.

        Args:
            order_type: 'MARKET' or 'LIMIT'
            order_price: Limit price (None for MARKET)
            current_price: Current market price
            quantity: Order quantity
            side: 'BUY' or 'SELL'
            fee_rate: Fee fraction (0.001 = 0.1%)
            slippage_bps: Expected slippage in basis points (MARKET only)

        Returns:
            dict: filled (bool), fill_price (Decimal|None), fill_quantity,
                  fee, slippage_amount, notional
        """
        if quantity <= 0:
            raise ValueError(f"quantity must be positive, got {quantity}")
        if current_price <= 0:
            raise ValueError(f"current_price must be positive, got {current_price}")

        if order_type == "MARKET":
            return self._fill_market(current_price, quantity, side, fee_rate, slippage_bps)
        elif order_type == "LIMIT":
            if order_price is None:
                raise ValueError("LIMIT order requires order_price")
            return self._fill_limit(order_price, current_price, quantity, side, fee_rate)
        else:
            raise ValueError(f"Unknown order_type: {order_type!r}")

    def _fill_market(
        self,
        current_price: Decimal,
        quantity: Decimal,
        side: str,
        fee_rate: Decimal,
        slippage_bps: Decimal,
    ) -> dict[str, Any]:
        """Market order: fills immediately with slippage."""
        slip_fraction = slippage_bps / Decimal("10000")
        slip_amount = current_price * slip_fraction

        if side == "BUY":
            fill_price = (current_price + slip_amount).quantize(PRICE_PRECISION)
        else:
            fill_price = (current_price - slip_amount).quantize(PRICE_PRECISION)

        notional = (fill_price * quantity).quantize(PRICE_PRECISION)
        fee = (notional * fee_rate).quantize(Decimal("0.00100000"))

        return {
            "filled": True,
            "fill_price": fill_price,
            "fill_quantity": quantity,
            "fee": fee,
            "slippage_amount": slip_amount.quantize(PRICE_PRECISION),
            "notional": notional,
            "order_type": "MARKET",
        }

    def _fill_limit(
        self,
        order_price: Decimal,
        current_price: Decimal,
        quantity: Decimal,
        side: str,
        fee_rate: Decimal,
    ) -> dict[str, Any]:
        """Limit order: fills only when market crosses limit price."""
        if side == "BUY":
            filled = current_price <= order_price
        else:  # SELL
            filled = current_price >= order_price

        if not filled:
            return {
                "filled": False,
                "fill_price": None,
                "fill_quantity": Decimal("0"),
                "fee": Decimal("0"),
                "slippage_amount": Decimal("0"),
                "notional": Decimal("0"),
                "order_type": "LIMIT",
            }

        fill_price = order_price
        notional = (fill_price * quantity).quantize(PRICE_PRECISION)
        fee = (notional * fee_rate).quantize(Decimal("0.00100000"))

        return {
            "filled": True,
            "fill_price": fill_price,
            "fill_quantity": quantity,
            "fee": fee,
            "slippage_amount": Decimal("0"),
            "notional": notional,
            "order_type": "LIMIT",
        }
