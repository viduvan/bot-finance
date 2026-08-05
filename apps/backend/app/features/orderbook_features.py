"""Order book feature computation.

Computes bid/ask imbalance, spread metrics, and depth-based
pressure signals from order book snapshots.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class OrderBookFeatures:
    """Computes order book depth features.

    Inputs: bid/ask depth data from Binance /depth endpoint.
    """

    def compute(self, book: dict) -> dict:
        """Compute order book features from depth snapshot.

        Args:
            book: dict with 'bids' and 'asks' lists of {'price': Decimal, 'quantity': Decimal}

        Returns:
            dict of order book features
        """
        bids = book.get("bids", [])
        asks = book.get("asks", [])

        if not bids or not asks:
            return {}

        result: dict[str, Any] = {}

        # Best bid/ask
        best_bid = Decimal(str(bids[0]["price"]))
        best_ask = Decimal(str(asks[0]["price"]))
        mid_price = (best_bid + best_ask) / 2

        result["best_bid"] = str(best_bid)
        result["best_ask"] = str(best_ask)
        result["mid_price"] = str(mid_price.quantize(Decimal("0.00000001")))

        # Spread
        spread = best_ask - best_bid
        result["spread_absolute"] = str(spread)
        if mid_price > 0:
            spread_bps = (spread / mid_price * 10000).quantize(Decimal("0.01"))
            result["spread_bps"] = str(spread_bps)
        else:
            result["spread_bps"] = None

        # Total bid/ask volume in top N levels
        top_n = min(10, len(bids), len(asks))

        total_bid_qty = sum(Decimal(str(b["quantity"])) for b in bids[:top_n])
        total_ask_qty = sum(Decimal(str(a["quantity"])) for a in asks[:top_n])

        result["bid_depth_qty"] = str(total_bid_qty.quantize(Decimal("0.00000001")))
        result["ask_depth_qty"] = str(total_ask_qty.quantize(Decimal("0.00000001")))

        # Bid/ask imbalance ratio
        # > 0 = more bids (buy pressure), < 0 = more asks (sell pressure)
        total_qty = total_bid_qty + total_ask_qty
        if total_qty > 0:
            imbalance = ((total_bid_qty - total_ask_qty) / total_qty * 100).quantize(
                Decimal("0.01")
            )
            result["order_imbalance_pct"] = str(imbalance)

            # Classify pressure
            if imbalance > 20:
                result["book_pressure"] = "STRONG_BUY"
            elif imbalance > 5:
                result["book_pressure"] = "BUY"
            elif imbalance < -20:
                result["book_pressure"] = "STRONG_SELL"
            elif imbalance < -5:
                result["book_pressure"] = "SELL"
            else:
                result["book_pressure"] = "NEUTRAL"
        else:
            result["order_imbalance_pct"] = None
            result["book_pressure"] = "NEUTRAL"

        # Bid/ask walls: detect unusually large orders near top of book
        result["bid_wall"] = self._detect_wall(bids, total_bid_qty, threshold=0.3)
        result["ask_wall"] = self._detect_wall(asks, total_ask_qty, threshold=0.3)

        # Cumulative volume up to 1% away from mid
        pct_1 = mid_price * Decimal("0.01")
        bid_1pct_qty = sum(
            Decimal(str(b["quantity"]))
            for b in bids
            if mid_price - Decimal(str(b["price"])) <= pct_1
        )
        ask_1pct_qty = sum(
            Decimal(str(a["quantity"]))
            for a in asks
            if Decimal(str(a["price"])) - mid_price <= pct_1
        )
        result["bid_qty_within_1pct"] = str(bid_1pct_qty.quantize(Decimal("0.00000001")))
        result["ask_qty_within_1pct"] = str(ask_1pct_qty.quantize(Decimal("0.00000001")))

        return result

    def _detect_wall(
        self,
        levels: list[dict],
        total_qty: Decimal,
        threshold: float = 0.3,
        max_levels: int = 5,
    ) -> bool:
        """Detect if any single level represents > threshold of total volume.

        A 'wall' is a large order that may act as support/resistance.
        """
        if total_qty <= 0:
            return False

        for level in levels[:max_levels]:
            qty = Decimal(str(level["quantity"]))
            if (qty / total_qty) > Decimal(str(threshold)):
                return True

        return False


# Shared singleton
orderbook_features = OrderBookFeatures()
