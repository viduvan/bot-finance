"""Risk/Reward ratio calculator."""

from __future__ import annotations

from decimal import Decimal


class RiskRewardCalculator:
    """Computes risk/reward ratio for a trade setup."""

    def calculate(
        self,
        entry: Decimal,
        stop_loss: Decimal,
        take_profit: Decimal,
    ) -> Decimal:
        """Calculate R/R ratio.

        R/R = |take_profit - entry| / |entry - stop_loss|

        Args:
            entry: Entry price
            stop_loss: Stop-loss price
            take_profit: Take-profit price

        Returns:
            Decimal: Risk/reward ratio (e.g. 2.0 = 2:1)
        """
        risk = abs(entry - stop_loss)
        if risk == 0:
            raise ValueError(
                f"stop_loss ({stop_loss}) cannot equal entry ({entry}) — zero risk distance"
            )

        reward = abs(take_profit - entry)
        rr = (reward / risk).quantize(Decimal("0.01"))
        return rr

    def meets_minimum(self, rr: Decimal, min_rr: Decimal) -> bool:
        """Check if R/R ratio meets the minimum required."""
        return rr >= min_rr
