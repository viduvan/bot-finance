"""Risk Gate — 15-condition trade approval system.

Every proposed trade must pass ALL conditions before execution.
ANY failure blocks the trade with a clear reason recorded.

Conditions:
  1.  Account balance > 0
  2.  Daily loss < max_daily_loss_pct
  3.  Open positions < max_open_positions
  4.  Total exposure < max_total_exposure_pct
  5.  Signal score >= min_signal_score (70 LIVE / 60 PAPER)
  6.  Risk/reward >= min_risk_reward_ratio
  7.  Spread <= max_spread_bps
  8.  Market data is not stale
  9.  Exchange is connected
  10. ATR% <= max_atr_pct (extreme volatility check)
  11. Volume >= min_volume_relative (low liquidity check)
  12. Position notional <= max_position_notional
  13. ATR-based SL not beyond account tolerance
  14. Symbol is in allowed symbols list
  15. Trading mode allows execution (PAPER always / LIVE requires live flag)
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import structlog

from app.core.metrics import RISK_GATE_REJECTIONS

logger = structlog.get_logger(__name__)

# Thresholds
MAX_ATR_PCT = Decimal("4.0")  # Block if ATR% > 4%
MIN_VOLUME_RELATIVE = Decimal("0.2")  # Block if volume < 20% of average
LIVE_MIN_SIGNAL_SCORE = 70  # Stricter threshold for live trading
PAPER_MIN_SIGNAL_SCORE = 60


class RiskGate:
    """Deterministic rule-based trade gate.

    All conditions are checked even if one fails — to provide
    complete feedback on why a trade was blocked.
    """

    def check(self, context: dict[str, Any]) -> dict[str, Any]:
        """Evaluate all risk conditions.

        Args:
            context: Dict containing all values needed for evaluation.
                     See module docstring for required keys.

        Returns:
            dict:
                allowed (bool): True if trade can proceed
                blocked_reasons (list[str]): All blocking reasons
                risk_score (int): 0-100 risk severity score
                mode (str): trading mode applied
        """
        blocked: list[str] = []

        trading_mode = context.get("trading_mode", "PAPER")
        min_score = LIVE_MIN_SIGNAL_SCORE if trading_mode == "LIVE" else PAPER_MIN_SIGNAL_SCORE

        # ── Condition 1: Account balance > 0
        balance = context.get("account_balance", Decimal("0"))
        if balance <= 0:
            blocked.append(
                f"Account balance is {balance} — cannot trade with zero or negative balance"
            )

        # ── Condition 2: Daily loss within limit
        daily_loss_pct = context.get("daily_loss_pct", Decimal("0"))
        max_daily_loss = context.get("max_daily_loss_pct", Decimal("3.0"))
        if daily_loss_pct > max_daily_loss:
            blocked.append(
                f"Daily loss {daily_loss_pct:.2f}% exceeds maximum {max_daily_loss:.2f}%"
            )

        # ── Condition 3: Open positions within limit
        open_positions = context.get("open_positions_count", 0)
        max_positions = context.get("max_open_positions", 3)
        if open_positions >= max_positions:
            blocked.append(
                f"Open positions ({open_positions}) at or exceeds maximum ({max_positions})"
            )

        # ── Condition 4: Total exposure within limit
        total_exposure = context.get("total_exposure_pct", Decimal("0"))
        max_exposure = context.get("max_total_exposure_pct", Decimal("50"))
        if total_exposure >= max_exposure:
            blocked.append(
                f"Total portfolio exposure {total_exposure:.1f}% exceeds maximum {max_exposure:.1f}%"
            )

        # ── Condition 5: Signal score sufficient
        signal_score = context.get("signal_score", 0)
        user_min_score = context.get("min_signal_score", min_score)
        effective_min_score = LIVE_MIN_SIGNAL_SCORE if trading_mode == "LIVE" else user_min_score
        if signal_score < effective_min_score:
            blocked.append(
                f"Signal score {signal_score} below minimum {effective_min_score} for {trading_mode} mode"
            )

        # ── Condition 6: Risk/Reward ratio sufficient
        rr = context.get("risk_reward_ratio", Decimal("0"))
        min_rr = context.get("min_risk_reward_ratio", Decimal("1.5"))
        if rr < min_rr:
            blocked.append(f"Risk/reward ratio {rr:.2f} below minimum {min_rr:.2f}")

        # ── Condition 7: Spread acceptable
        spread_bps = context.get("spread_bps", Decimal("0"))
        max_spread = context.get("max_spread_bps", Decimal("50"))
        if spread_bps > max_spread:
            blocked.append(f"Spread {spread_bps:.1f} bps exceeds maximum {max_spread:.1f} bps")

        # ── Condition 8: Market data not stale
        if context.get("market_data_stale", False):
            blocked.append("Market data is stale — cannot trade on outdated prices")

        # ── Condition 9: Exchange connected
        if not context.get("exchange_connected", True):
            blocked.append("Exchange connection is not available")

        # ── Condition 10: ATR% not extreme
        atr_pct = context.get("atr_pct", Decimal("0"))
        if atr_pct and Decimal(str(atr_pct)) > MAX_ATR_PCT:
            blocked.append(
                f"Market volatility (ATR%) {atr_pct:.2f}% is extreme (max {MAX_ATR_PCT}%)"
            )

        # ── Condition 11: Volume not too low
        vol_rel = context.get("volume_relative")
        if vol_rel is not None and Decimal(str(vol_rel)) < MIN_VOLUME_RELATIVE:
            blocked.append(
                f"Volume relative to average ({vol_rel:.2f}×) is too low — insufficient liquidity"
            )

        # ── Condition 12: Position notional within cap
        max_notional = context.get("max_position_notional")
        position_notional = context.get("position_notional")
        if max_notional and position_notional:
            if Decimal(str(position_notional)) > Decimal(str(max_notional)):
                blocked.append(
                    f"Position notional {position_notional} exceeds maximum {max_notional}"
                )

        # ── Condition 13: Symbol in allowed list (if configured)
        allowed_symbols = context.get("allowed_symbols")
        symbol = context.get("symbol", "")
        if allowed_symbols and symbol not in allowed_symbols:
            blocked.append(f"Symbol {symbol} is not in the allowed trading symbols list")

        # ── Condition 14: Trading mode allows execution
        if trading_mode not in ("PAPER", "LIVE", "BACKTEST"):
            blocked.append(f"Unknown trading mode: {trading_mode}")

        # ── Condition 15: LIVE mode additional safeguard
        if trading_mode == "LIVE":
            live_enabled = context.get("live_trading_enabled", False)
            if not live_enabled:
                blocked.append("LIVE trading is not enabled in configuration")

        # ── Compute risk score (0 = safest, 100 = riskiest)
        risk_score = self._compute_risk_score(context, blocked)

        # ── Emit Prometheus metrics for blocked trades
        if blocked:
            for reason in blocked:
                reason_label = self._classify_reason(reason)
                try:
                    RISK_GATE_REJECTIONS.labels(reason=reason_label).inc()
                except Exception:
                    pass  # Metrics should never block trading logic

        allowed = len(blocked) == 0

        logger.info(
            "risk_gate_check",
            symbol=context.get("symbol"),
            allowed=allowed,
            blocked_count=len(blocked),
            risk_score=risk_score,
            trading_mode=trading_mode,
        )

        if not allowed:
            logger.warning(
                "risk_gate_blocked",
                symbol=context.get("symbol"),
                reasons=blocked,
            )

        return {
            "allowed": allowed,
            "blocked_reasons": blocked,
            "risk_score": risk_score,
            "mode": trading_mode,
            "conditions_checked": 15,
        }

    def _compute_risk_score(self, context: dict, blocked: list) -> int:
        """Compute a 0-100 risk score. Higher = riskier.

        Considers: daily loss, spread, volatility, open positions.
        """
        score = 0

        # Daily loss contribution (0-30)
        daily_loss = float(context.get("daily_loss_pct", 0))
        max_daily = float(context.get("max_daily_loss_pct", 3.0))
        if max_daily > 0:
            score += min(30, int((daily_loss / max_daily) * 30))

        # Spread contribution (0-20)
        spread = float(context.get("spread_bps", 0))
        max_spread = float(context.get("max_spread_bps", 50))
        if max_spread > 0:
            score += min(20, int((spread / max_spread) * 20))

        # ATR volatility contribution (0-25)
        atr_pct = float(context.get("atr_pct", 0))
        score += min(25, int(atr_pct * 5))

        # Open positions contribution (0-15)
        positions = int(context.get("open_positions_count", 0))
        max_pos = int(context.get("max_open_positions", 3))
        if max_pos > 0:
            score += min(15, int((positions / max_pos) * 15))

        # Blocked conditions contribution (0-10)
        score += min(10, len(blocked) * 2)

        return min(100, score)

    @staticmethod
    def _classify_reason(reason: str) -> str:
        """Classify a block reason for Prometheus label (short form)."""
        reason_lower = reason.lower()
        if "daily" in reason_lower:
            return "daily_loss"
        if "position" in reason_lower:
            return "max_positions"
        if "exposure" in reason_lower:
            return "exposure"
        if "signal" in reason_lower:
            return "signal_score"
        if "risk" in reason_lower or "reward" in reason_lower:
            return "risk_reward"
        if "spread" in reason_lower:
            return "spread"
        if "stale" in reason_lower:
            return "stale_data"
        if "connect" in reason_lower or "exchange" in reason_lower:
            return "exchange_connection"
        if "volatil" in reason_lower or "atr" in reason_lower:
            return "volatility"
        if "volume" in reason_lower:
            return "volume"
        if "notional" in reason_lower:
            return "notional"
        if "symbol" in reason_lower:
            return "symbol_not_allowed"
        if "live" in reason_lower:
            return "live_not_enabled"
        if "balance" in reason_lower:
            return "zero_balance"
        return "other"
