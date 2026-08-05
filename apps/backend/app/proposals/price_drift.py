"""Price Drift Guard — detect price drift requiring re-confirmation.

If the market price moves more than max_drift_bps (basis points) from the
approved price, the human must re-confirm before execution proceeds.
This prevents executing at a significantly different price than approved.

Default: 20 bps (0.2%) from config.max_price_drift_bps.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import structlog

from app.config import settings

logger = structlog.get_logger(__name__)


class PriceDriftGuard:
    """Detects significant price movement between approval and execution."""

    def __init__(self, max_drift_bps: float | None = None) -> None:
        self.max_drift_bps = Decimal(
            str(max_drift_bps if max_drift_bps is not None else settings.max_price_drift_bps)
        )

    def check(
        self,
        approved_price: Decimal,
        current_price: Decimal,
    ) -> dict[str, Any]:
        """Check if current price has drifted beyond threshold.

        Args:
            approved_price: Price when user approved the trade
            current_price: Current market price

        Returns:
            dict: requires_reconfirm (bool), drift_bps (float), direction (str)
        """
        if approved_price <= 0:
            return {
                "requires_reconfirm": True,
                "drift_bps": 0,
                "direction": "UNKNOWN",
                "reason": "Invalid approved price",
            }

        drift = (current_price - approved_price) / approved_price * 10000  # In basis points
        drift_bps = abs(drift)
        drift_direction = "UP" if drift > 0 else ("DOWN" if drift < 0 else "NONE")

        requires_reconfirm = drift_bps > self.max_drift_bps

        if requires_reconfirm:
            logger.warning(
                "price_drift_reconfirm_required",
                approved_price=str(approved_price),
                current_price=str(current_price),
                drift_bps=float(drift_bps),
                max_drift_bps=float(self.max_drift_bps),
            )

        return {
            "requires_reconfirm": requires_reconfirm,
            "drift_bps": float(drift_bps),
            "drift_direction": drift_direction,
            "approved_price": str(approved_price),
            "current_price": str(current_price),
            "max_drift_bps": float(self.max_drift_bps),
        }
