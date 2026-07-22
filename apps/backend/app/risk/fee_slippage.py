"""Fee and Slippage Estimator — Binance cost model."""

from __future__ import annotations

from decimal import Decimal

BINANCE_MAKER_FEE = Decimal("0.001")    # 0.1%
BINANCE_TAKER_FEE = Decimal("0.001")    # 0.1% (standard tier)


class FeeSlippageEstimator:
    """Estimates trading costs: exchange fees + market slippage.

    Fee model: Binance standard — 0.1% maker/taker
    Slippage model: half of bid/ask spread (simple model)
    """

    def estimate(
        self,
        notional: Decimal,
        order_type: str = "LIMIT",
        spread_bps: Decimal = Decimal("5"),
        maker_fee: Decimal = BINANCE_MAKER_FEE,
        taker_fee: Decimal = BINANCE_TAKER_FEE,
    ) -> dict:
        """Estimate single-side trade cost.

        Args:
            notional: Order notional value (qty × price)
            order_type: 'LIMIT' (maker) or 'MARKET' (taker)
            spread_bps: Current bid/ask spread in basis points
            maker_fee: Maker fee rate (default 0.001 = 0.1%)
            taker_fee: Taker fee rate (default 0.001 = 0.1%)

        Returns:
            dict: fee, slippage, total_cost, fee_rate
        """
        if notional < 0:
            raise ValueError(f"notional cannot be negative, got {notional}")

        if notional == 0:
            return {
                "fee": Decimal("0"),
                "slippage": Decimal("0"),
                "total_cost": Decimal("0"),
                "fee_rate": Decimal("0"),
            }

        fee_rate = maker_fee if order_type == "LIMIT" else taker_fee
        fee = (notional * fee_rate).quantize(Decimal("0.00000001"))

        # Slippage = half of spread (expected fill cost above mid)
        spread_decimal = spread_bps / Decimal("10000")
        slippage = (notional * spread_decimal / 2).quantize(Decimal("0.00000001"))

        total_cost = fee + slippage

        return {
            "fee": fee,
            "slippage": slippage,
            "total_cost": total_cost,
            "fee_rate": fee_rate,
        }

    def estimate_round_trip(
        self,
        notional: Decimal,
        order_type: str = "LIMIT",
        spread_bps: Decimal = Decimal("5"),
    ) -> dict:
        """Estimate round-trip (open + close) total cost."""
        single = self.estimate(notional, order_type, spread_bps)
        round_trip = single["total_cost"] * 2

        return {
            **single,
            "round_trip_cost": round_trip,
            "round_trip_fee": single["fee"] * 2,
            "round_trip_slippage": single["slippage"] * 2,
        }
