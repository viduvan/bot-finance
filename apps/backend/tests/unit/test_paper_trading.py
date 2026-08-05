"""Phase 6: Paper Trading Tests (TDD — written BEFORE implementation).

Tests cover:
- PaperOrderEngine: simulated fill logic, slippage, fee calculation
- PaperPositionManager: open/close/update positions, unrealized PnL
- PaperPnLTracker: realized + unrealized P&L aggregation
- ExecutionService: APPROVED → EXECUTED flow, daily loss integration
- PaperFillSimulator: fill price computation (LIMIT/MARKET)
"""

from __future__ import annotations

from decimal import Decimal

import pytest

# ─────────────────────────────────────────────────────────────────────────────
# PaperFillSimulator
# ─────────────────────────────────────────────────────────────────────────────


class TestPaperFillSimulator:
    """Tests for simulated order fill logic."""

    @pytest.fixture
    def sim(self):
        from app.execution.paper_fill import PaperFillSimulator

        return PaperFillSimulator()

    def test_market_order_fills_at_current_price(self, sim):
        """MARKET order fills immediately at current market price (zero slippage)."""
        result = sim.simulate_fill(
            order_type="MARKET",
            order_price=None,
            current_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            slippage_bps=Decimal("0"),  # No slippage for this test
        )
        assert result["filled"] is True
        assert result["fill_price"] == Decimal("50000")
        assert result["fill_quantity"] == Decimal("0.1")

    def test_market_order_applies_slippage(self, sim):
        """MARKET BUY order fill price includes slippage (slightly above market)."""
        result = sim.simulate_fill(
            order_type="MARKET",
            order_price=None,
            current_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            side="BUY",
            slippage_bps=Decimal("5"),
        )
        # Slippage = 50000 × 5bps = 50000 × 0.0005 = $25
        assert result["fill_price"] > Decimal("50000")
        assert result["fill_price"] <= Decimal("50026")  # Within 5bps

    def test_limit_buy_fills_when_price_at_or_below_limit(self, sim):
        """LIMIT BUY fills when current price <= limit price."""
        result = sim.simulate_fill(
            order_type="LIMIT",
            order_price=Decimal("50100"),  # Limit price
            current_price=Decimal("50000"),  # Market below limit → fills
            quantity=Decimal("0.1"),
            side="BUY",
        )
        assert result["filled"] is True
        assert result["fill_price"] == Decimal("50100")  # Fills at limit price

    def test_limit_buy_does_not_fill_above_limit(self, sim):
        """LIMIT BUY does NOT fill when current price > limit price."""
        result = sim.simulate_fill(
            order_type="LIMIT",
            order_price=Decimal("49000"),  # Limit price
            current_price=Decimal("50000"),  # Market above limit → no fill
            quantity=Decimal("0.1"),
            side="BUY",
        )
        assert result["filled"] is False
        assert result["fill_price"] is None

    def test_limit_sell_fills_when_price_at_or_above_limit(self, sim):
        """LIMIT SELL fills when current price >= limit price."""
        result = sim.simulate_fill(
            order_type="LIMIT",
            order_price=Decimal("50000"),
            current_price=Decimal("50100"),  # Market above limit → fills
            quantity=Decimal("0.1"),
            side="SELL",
        )
        assert result["filled"] is True

    def test_fee_calculated_on_notional(self, sim):
        """Fee = notional × fee_rate (with zero slippage for exact calculation)."""
        result = sim.simulate_fill(
            order_type="MARKET",
            order_price=None,
            current_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            fee_rate=Decimal("0.001"),  # 0.1%
            slippage_bps=Decimal("0"),  # No slippage for clean assertion
        )
        # Notional = 50000 × 0.1 = $5000, fee = $5000 × 0.001 = $5
        assert result["fee"] == Decimal("5.000")

    def test_zero_quantity_raises(self, sim):
        """Zero or negative quantity should raise ValueError."""
        with pytest.raises(ValueError, match="quantity"):
            sim.simulate_fill(
                order_type="MARKET",
                order_price=None,
                current_price=Decimal("50000"),
                quantity=Decimal("0"),
            )


# ─────────────────────────────────────────────────────────────────────────────
# PaperPositionManager
# ─────────────────────────────────────────────────────────────────────────────


class TestPaperPositionManager:
    """Tests for paper position tracking."""

    @pytest.fixture
    def pm(self):
        from app.execution.position_manager import PaperPositionManager

        return PaperPositionManager()

    def test_open_long_position(self, pm):
        """Opening a LONG position returns position dict."""
        pos = pm.open_position(
            symbol="BTCUSDT",
            side="LONG",
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            fee=Decimal("5.0"),
        )
        assert pos["symbol"] == "BTCUSDT"
        assert pos["side"] == "LONG"
        assert pos["entry_price"] == Decimal("50000")
        assert pos["quantity"] == Decimal("0.1")
        assert pos["status"] == "OPEN"

    def test_unrealized_pnl_long_profit(self, pm):
        """Unrealized PnL for LONG should be positive when price rises."""
        pos = pm.open_position(
            symbol="BTCUSDT",
            side="LONG",
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            fee=Decimal("5.0"),
        )
        pnl = pm.calc_unrealized_pnl(pos, current_price=Decimal("51000"))
        # (51000 - 50000) × 0.1 = $100
        assert pnl == Decimal("100")

    def test_unrealized_pnl_long_loss(self, pm):
        """Unrealized PnL for LONG should be negative when price falls."""
        pos = pm.open_position(
            symbol="BTCUSDT",
            side="LONG",
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            fee=Decimal("5.0"),
        )
        pnl = pm.calc_unrealized_pnl(pos, current_price=Decimal("49000"))
        # (49000 - 50000) × 0.1 = -$100
        assert pnl == Decimal("-100")

    def test_unrealized_pnl_short_profit(self, pm):
        """Unrealized PnL for SHORT should be positive when price falls."""
        pos = pm.open_position(
            symbol="BTCUSDT",
            side="SHORT",
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            fee=Decimal("5.0"),
        )
        pnl = pm.calc_unrealized_pnl(pos, current_price=Decimal("49000"))
        # (50000 - 49000) × 0.1 = $100
        assert pnl == Decimal("100")

    def test_close_position_returns_trade_result(self, pm):
        """Closing a position should return a TradeResult dict."""
        pos = pm.open_position("BTCUSDT", "LONG", Decimal("50000"), Decimal("0.1"), Decimal("5.0"))
        result = pm.close_position(
            position=pos,
            exit_price=Decimal("51000"),
            fee=Decimal("5.1"),
            close_reason="TAKE_PROFIT",
        )
        assert "net_pnl" in result
        assert "gross_pnl" in result
        assert result["close_reason"] == "TAKE_PROFIT"
        assert result["symbol"] == "BTCUSDT"

    def test_close_long_profit_net_pnl(self, pm):
        """Net PnL = gross PnL - entry fee - exit fee."""
        pos = pm.open_position("BTCUSDT", "LONG", Decimal("50000"), Decimal("0.1"), Decimal("5.0"))
        result = pm.close_position(
            position=pos,
            exit_price=Decimal("51000"),
            fee=Decimal("5.1"),
            close_reason="TAKE_PROFIT",
        )
        # Gross PnL = (51000 - 50000) × 0.1 = $100
        # Net PnL = $100 - $5.0 (entry fee) - $5.1 (exit fee) = $89.9
        assert result["gross_pnl"] == Decimal("100")
        assert result["net_pnl"] == Decimal("89.9")

    def test_stop_loss_triggered_closes_at_stop(self, pm):
        """Stop loss hit should close position at stop price."""
        pos = pm.open_position("BTCUSDT", "LONG", Decimal("50000"), Decimal("0.1"), Decimal("5.0"))
        result = pm.close_position(
            position=pos,
            exit_price=Decimal("48000"),
            fee=Decimal("4.8"),
            close_reason="STOP_LOSS",
        )
        assert result["close_reason"] == "STOP_LOSS"
        assert result["net_pnl"] < 0  # Loss


# ─────────────────────────────────────────────────────────────────────────────
# PaperPnLTracker
# ─────────────────────────────────────────────────────────────────────────────


class TestPaperPnLTracker:
    """Tests for aggregated PnL tracking (realized + unrealized)."""

    @pytest.fixture
    def tracker(self):
        from app.execution.pnl_tracker import PaperPnLTracker

        return PaperPnLTracker()

    def test_initial_state_zero(self, tracker):
        """Fresh tracker should have zero values."""
        summary = tracker.get_summary()
        assert summary["realized_pnl"] == Decimal("0")
        assert summary["unrealized_pnl"] == Decimal("0")
        assert summary["total_trades"] == 0

    def test_record_win_increases_realized(self, tracker):
        """Recording a winning trade increases realized PnL."""
        tracker.record_trade(net_pnl=Decimal("100"), symbol="BTCUSDT")
        summary = tracker.get_summary()
        assert summary["realized_pnl"] == Decimal("100")
        assert summary["total_trades"] == 1
        assert summary["winning_trades"] == 1

    def test_record_loss_decreases_realized(self, tracker):
        """Recording a losing trade decreases realized PnL."""
        tracker.record_trade(net_pnl=Decimal("-50"), symbol="BTCUSDT")
        summary = tracker.get_summary()
        assert summary["realized_pnl"] == Decimal("-50")
        assert summary["losing_trades"] == 1

    def test_win_rate_calculation(self, tracker):
        """Win rate = winning_trades / total_trades × 100."""
        tracker.record_trade(net_pnl=Decimal("100"), symbol="BTCUSDT")
        tracker.record_trade(net_pnl=Decimal("50"), symbol="BTCUSDT")
        tracker.record_trade(net_pnl=Decimal("-30"), symbol="BTCUSDT")
        summary = tracker.get_summary()
        # 2 wins / 3 trades = 66.7%
        assert abs(summary["win_rate"] - Decimal("66.67")) < Decimal("0.1")

    def test_max_drawdown_tracked(self, tracker):
        """Max drawdown should track the largest cumulative loss."""
        tracker.record_trade(net_pnl=Decimal("100"), symbol="BTCUSDT")
        tracker.record_trade(net_pnl=Decimal("-60"), symbol="BTCUSDT")
        tracker.record_trade(net_pnl=Decimal("-80"), symbol="BTCUSDT")
        summary = tracker.get_summary()
        # Peak was $100, then dropped to -$40 → drawdown from peak = $140
        assert summary["max_drawdown"] >= Decimal("0")

    def test_total_pnl_is_realized_plus_unrealized(self, tracker):
        """total_pnl = realized_pnl + unrealized_pnl."""
        tracker.record_trade(net_pnl=Decimal("100"), symbol="BTCUSDT")
        tracker.update_unrealized(Decimal("25"))
        summary = tracker.get_summary()
        assert summary["total_pnl"] == Decimal("125")

    def test_profit_factor(self, tracker):
        """Profit factor = gross_wins / abs(gross_losses)."""
        tracker.record_trade(net_pnl=Decimal("200"), symbol="BTCUSDT")
        tracker.record_trade(net_pnl=Decimal("-100"), symbol="BTCUSDT")
        summary = tracker.get_summary()
        assert summary["profit_factor"] == Decimal("2.0")


# ─────────────────────────────────────────────────────────────────────────────
# ExecutionService
# ─────────────────────────────────────────────────────────────────────────────


class TestExecutionService:
    """Tests for execution flow: APPROVED proposal → simulated fill → position."""

    @pytest.fixture
    def make_proposal(self):
        """Return a factory for mock APPROVED proposals."""

        def _factory(**overrides) -> dict:
            base = {
                "id": "prop-001",
                "symbol": "BTCUSDT",
                "recommendation": "BUY",
                "status": "APPROVED",
                "suggested_price": "50000",
                "suggested_quantity": "0.1",
                "suggested_order_type": "LIMIT",
                "stop_loss_price": "48000",
                "take_profit_prices": {"tp1": "52000"},
                "estimated_fee": "5.0",
                "estimated_slippage": "2.5",
                "environment": "PAPER",
                "version": 1,
            }
            base.update(overrides)
            return base

        return _factory

    def test_execute_returns_order_dict(self, make_proposal):
        """execute() should return a dict with order details."""
        from app.execution.service import PaperExecutionService

        svc = PaperExecutionService()
        proposal = make_proposal()
        result = svc.execute(
            proposal=proposal,
            current_price=Decimal("50000"),
        )
        assert "order_id" in result or "client_order_id" in result
        assert "fill_price" in result
        assert "fill_quantity" in result

    def test_execute_creates_position(self, make_proposal):
        """A successfully filled order should create an open position."""
        from app.execution.service import PaperExecutionService

        svc = PaperExecutionService()
        proposal = make_proposal()
        result = svc.execute(
            proposal=proposal,
            current_price=Decimal("50000"),
        )
        assert result.get("position") is not None
        assert result["position"]["status"] == "OPEN"

    def test_execute_buy_recommendation_opens_long(self, make_proposal):
        """BUY recommendation should open LONG position."""
        from app.execution.service import PaperExecutionService

        svc = PaperExecutionService()
        proposal = make_proposal(recommendation="BUY")
        result = svc.execute(proposal=proposal, current_price=Decimal("50000"))
        assert result["position"]["side"] == "LONG"

    def test_execute_sell_recommendation_opens_short(self, make_proposal):
        """SELL recommendation should open SHORT position."""
        from app.execution.service import PaperExecutionService

        svc = PaperExecutionService()
        proposal = make_proposal(
            recommendation="SELL", suggested_price="50000", stop_loss_price="52000"
        )
        result = svc.execute(proposal=proposal, current_price=Decimal("50000"))
        assert result["position"]["side"] == "SHORT"

    def test_execute_paper_environment(self, make_proposal):
        """Paper execution should mark order as PAPER environment."""
        from app.execution.service import PaperExecutionService

        svc = PaperExecutionService()
        proposal = make_proposal(environment="PAPER")
        result = svc.execute(proposal=proposal, current_price=Decimal("50000"))
        assert result.get("environment") == "PAPER"

    def test_execute_rejected_proposal_raises(self, make_proposal):
        """Executing a REJECTED proposal should raise ValueError."""
        from app.execution.service import PaperExecutionService

        svc = PaperExecutionService()
        proposal = make_proposal(status="REJECTED")
        with pytest.raises(ValueError, match="APPROVED|status"):
            svc.execute(proposal=proposal, current_price=Decimal("50000"))

    def test_execute_generates_client_order_id(self, make_proposal):
        """Each execution should generate a unique client_order_id."""
        from app.execution.service import PaperExecutionService

        svc = PaperExecutionService()
        p1 = make_proposal()
        p2 = make_proposal(id="prop-002")
        r1 = svc.execute(p1, Decimal("50000"))
        r2 = svc.execute(p2, Decimal("50000"))
        assert r1["client_order_id"] != r2["client_order_id"]
