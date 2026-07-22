"""Exchange Filter — Binance LOT_SIZE, PRICE_FILTER, MIN_NOTIONAL enforcement.

Binance requires all orders to satisfy exchange-specific filters.
Failing to apply these results in rejected orders.

Filters applied:
- LOT_SIZE: quantity must be within [min_qty, max_qty] and a multiple of step_size
- PRICE_FILTER: price must be a multiple of tick_size
- MIN_NOTIONAL: qty × price >= min_notional
"""

from __future__ import annotations

from decimal import ROUND_DOWN, Decimal

import structlog

logger = structlog.get_logger(__name__)


class ExchangeFilter:
    """Enforces Binance exchange trading rules on quantity and price."""

    def apply(
        self,
        quantity: Decimal,
        price: Decimal,
        filters: dict,
    ) -> dict:
        """Apply all exchange filters to a proposed order.

        Args:
            quantity: Proposed order quantity
            price: Proposed order price
            filters: dict containing step_size, min_qty, max_qty,
                     tick_size, min_notional

        Returns:
            dict: adjusted quantity, price, notional

        Raises:
            ValueError: if quantity or notional violates hard limits
        """
        step_size: Decimal = filters["step_size"]
        min_qty: Decimal = filters["min_qty"]
        max_qty: Decimal = filters["max_qty"]
        tick_size: Decimal = filters["tick_size"]
        min_notional: Decimal = filters["min_notional"]

        # 1. Round quantity DOWN to nearest step_size
        adjusted_qty = self._floor_to_step(quantity, step_size)

        # 2. Validate quantity bounds
        if adjusted_qty < min_qty:
            raise ValueError(
                f"quantity {adjusted_qty} is below minimum allowed ({min_qty})"
            )
        if adjusted_qty > max_qty:
            raise ValueError(
                f"quantity {adjusted_qty} exceeds maximum allowed ({max_qty})"
            )

        # 3. Round price to nearest tick_size (floor)
        adjusted_price = self._floor_to_step(price, tick_size)

        # 4. Check min notional
        notional = (adjusted_qty * adjusted_price).quantize(Decimal("0.00000001"))
        if notional < min_notional:
            raise ValueError(
                f"notional {notional} is below minimum required ({min_notional})"
            )

        logger.debug(
            "exchange_filter_applied",
            original_qty=str(quantity),
            adjusted_qty=str(adjusted_qty),
            original_price=str(price),
            adjusted_price=str(adjusted_price),
            notional=str(notional),
        )

        return {
            "quantity": adjusted_qty,
            "price": adjusted_price,
            "notional": notional,
            "qty_adjusted": adjusted_qty != quantity,
            "price_adjusted": adjusted_price != price,
        }

    @staticmethod
    def _floor_to_step(value: Decimal, step: Decimal) -> Decimal:
        """Floor value to the nearest multiple of step."""
        if step <= 0:
            return value
        return (value // step * step).quantize(step, rounding=ROUND_DOWN)
