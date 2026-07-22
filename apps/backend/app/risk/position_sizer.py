"""Position Sizer — Fixed-risk position sizing formula.

Formula:
    risk_amount = account_balance × risk_pct
    sl_distance = |entry_price - stop_loss|
    quantity    = risk_amount / sl_distance

Caps applied:
    - risk_pct <= MAX_RISK_PCT (5%)
    - notional <= MAX_POSITION_PCT × account_balance (20%)
"""

from __future__ import annotations

from decimal import ROUND_DOWN, Decimal

import structlog

logger = structlog.get_logger(__name__)

MAX_RISK_PCT = Decimal("0.05")          # 5% max risk per trade
MAX_POSITION_PCT = Decimal("0.20")     # 20% max notional per trade
QUANTITY_PRECISION = Decimal("0.00001000")  # 8 decimal places


class PositionSizer:
    """Computes position size using a fixed-risk money management approach.

    All inputs and outputs are Decimal to preserve financial precision.
    """

    def calculate(
        self,
        account_balance: Decimal,
        risk_pct: Decimal,
        entry_price: Decimal,
        stop_loss: Decimal,
        direction: str,
        max_risk_pct: Decimal = MAX_RISK_PCT,
        max_position_pct: Decimal = MAX_POSITION_PCT,
    ) -> dict:
        """Calculate position size.

        Args:
            account_balance: Total account balance in quote currency (e.g. USDT)
            risk_pct: Fraction of account to risk (e.g. 0.01 = 1%)
            entry_price: Planned entry price
            stop_loss: Stop-loss price
            direction: 'LONG' or 'SHORT'
            max_risk_pct: Hard cap on risk percentage (default 5%)
            max_position_pct: Hard cap on position notional vs balance (default 20%)

        Returns:
            dict with: quantity, risk_amount, notional_value, sl_distance,
                       was_capped, cap_reason
        """
        self._validate_inputs(account_balance, risk_pct, entry_price, stop_loss, direction, max_risk_pct)

        # Core formula
        risk_amount = account_balance * risk_pct
        sl_distance = abs(entry_price - stop_loss)
        raw_quantity = risk_amount / sl_distance

        # Apply notional cap
        max_notional = account_balance * max_position_pct
        raw_notional = raw_quantity * entry_price

        was_capped = False
        cap_reason = None

        if raw_notional > max_notional:
            raw_quantity = max_notional / entry_price
            was_capped = True
            cap_reason = f"Notional {raw_notional:.2f} exceeds {max_position_pct*100:.0f}% of balance"
            logger.warning(
                "position_size_capped",
                raw_notional=str(raw_notional),
                max_notional=str(max_notional),
                reason=cap_reason,
            )

        # Round down to avoid over-sizing
        quantity = raw_quantity.quantize(QUANTITY_PRECISION, rounding=ROUND_DOWN)
        notional_value = quantity * entry_price

        logger.info(
            "position_sized",
            direction=direction,
            entry=str(entry_price),
            sl=str(stop_loss),
            sl_distance=str(sl_distance),
            quantity=str(quantity),
            risk_amount=str(risk_amount),
            notional=str(notional_value),
            was_capped=was_capped,
        )

        return {
            "quantity": quantity,
            "risk_amount": risk_amount,
            "notional_value": notional_value,
            "sl_distance": sl_distance,
            "was_capped": was_capped,
            "cap_reason": cap_reason,
        }

    def _validate_inputs(
        self,
        account_balance: Decimal,
        risk_pct: Decimal,
        entry_price: Decimal,
        stop_loss: Decimal,
        direction: str,
        max_risk_pct: Decimal,
    ) -> None:
        """Validate all inputs before calculation."""
        if account_balance <= 0:
            raise ValueError(f"account_balance must be positive, got {account_balance}")

        if risk_pct <= 0:
            raise ValueError(f"risk_pct must be positive, got {risk_pct}")

        if risk_pct > max_risk_pct:
            raise ValueError(
                f"risk_pct {risk_pct} exceeds maximum allowed {max_risk_pct} "
                f"({float(max_risk_pct)*100:.0f}%)"
            )

        if entry_price <= 0:
            raise ValueError(f"entry_price must be positive, got {entry_price}")

        if stop_loss <= 0:
            raise ValueError(f"stop_loss must be positive, got {stop_loss}")

        sl_distance = abs(entry_price - stop_loss)
        if sl_distance == 0:
            raise ValueError(
                "stop_loss cannot equal entry_price — zero stop distance would create infinite position"
            )

        if direction == "LONG" and stop_loss >= entry_price:
            raise ValueError(
                f"LONG stop_loss ({stop_loss}) must be below entry_price ({entry_price})"
            )

        if direction == "SHORT" and stop_loss <= entry_price:
            raise ValueError(
                f"SHORT stop_loss ({stop_loss}) must be above entry_price ({entry_price})"
            )
