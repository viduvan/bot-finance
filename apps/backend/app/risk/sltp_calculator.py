"""SL/TP Calculator — ATR-based stop-loss and take-profit levels."""

from __future__ import annotations

from decimal import Decimal

import structlog

logger = structlog.get_logger(__name__)


class SLTPCalculator:
    """Computes stop-loss and take-profit prices using ATR as the base unit.

    Stop Loss:  entry ± (atr_multiplier × ATR)
    Take Profit: entry ± (sl_distance × risk_reward)
    """

    def calculate(
        self,
        entry_price: Decimal,
        atr: Decimal,
        direction: str,
        atr_multiplier: Decimal = Decimal("1.5"),
        risk_reward: Decimal = Decimal("2.0"),
    ) -> dict:
        """Compute SL and TP prices.

        Args:
            entry_price: Planned entry price
            atr: Current ATR value (in price units)
            direction: 'LONG' or 'SHORT'
            atr_multiplier: How many ATR widths to place SL (default 1.5)
            risk_reward: Desired R/R ratio (default 2.0)

        Returns:
            dict: stop_loss, take_profit, sl_distance, tp_distance, risk_pct
        """
        if atr <= 0:
            raise ValueError(f"atr must be positive, got {atr}")
        if entry_price <= 0:
            raise ValueError(f"entry_price must be positive, got {entry_price}")
        if risk_reward <= 0:
            raise ValueError(f"risk_reward must be positive, got {risk_reward}")

        sl_distance = (atr * atr_multiplier).quantize(Decimal("0.00000001"))
        tp_distance = (sl_distance * risk_reward).quantize(Decimal("0.00000001"))

        if direction == "LONG":
            stop_loss = (entry_price - sl_distance).quantize(Decimal("0.00000001"))
            take_profit = (entry_price + tp_distance).quantize(Decimal("0.00000001"))
        elif direction == "SHORT":
            stop_loss = (entry_price + sl_distance).quantize(Decimal("0.00000001"))
            take_profit = (entry_price - tp_distance).quantize(Decimal("0.00000001"))
        else:
            raise ValueError(f"direction must be 'LONG' or 'SHORT', got {direction!r}")

        # Risk as percentage of entry
        risk_pct = (sl_distance / entry_price * 100).quantize(Decimal("0.01"))

        logger.debug(
            "sltp_calculated",
            direction=direction,
            entry=str(entry_price),
            stop_loss=str(stop_loss),
            take_profit=str(take_profit),
            sl_distance=str(sl_distance),
            risk_pct=str(risk_pct),
        )

        return {
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "sl_distance": sl_distance,
            "tp_distance": tp_distance,
            "risk_pct": risk_pct,
            "atr_multiplier": atr_multiplier,
            "risk_reward": risk_reward,
        }
