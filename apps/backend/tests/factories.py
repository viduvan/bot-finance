"""Factory Boy factories for test data generation.

Usage in tests:
    user = await UserFactory.create(db_session)
    proposal = await ProposalFactory.create(db_session, symbol="BTCUSDT")
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.core.security import hash_password
from app.models.user import User
from app.models.proposal import TradeProposal
from app.models.order import Order
from app.models.agent import AgentWorkflow, AgentRun


class UserFactory:
    """Create test users."""

    _counter = 0

    @classmethod
    async def create(
        cls,
        db,
        email: str | None = None,
        password: str = "TestPassword123!",
        role: str = "TRADER",
        mfa_enabled: bool = False,
        is_active: bool = True,
    ) -> User:
        cls._counter += 1
        user = User(
            id=uuid.uuid4(),
            email=email or f"user{cls._counter}@acta.test",
            password_hash=hash_password(password),
            role=role,
            is_active=is_active,
            mfa_enabled=mfa_enabled,
        )
        db.add(user)
        await db.flush()
        return user

    @classmethod
    async def create_admin(cls, db, **kwargs) -> User:
        return await cls.create(db, role="ADMIN", email="admin@acta.test", **kwargs)

    @classmethod
    async def create_viewer(cls, db, **kwargs) -> User:
        return await cls.create(db, role="VIEWER", **kwargs)


class ProposalFactory:
    """Create test trade proposals."""

    @classmethod
    async def create(
        cls,
        db,
        symbol: str = "BTCUSDT",
        recommendation: str = "BUY",
        status: str = "WAITING_FOR_HUMAN",
        entry_price: float = 50000.0,
        stop_loss: float = 49000.0,
        take_profit: float = 53000.0,
        confidence: float = 0.72,
        environment: str = "PAPER",
        expires_in_minutes: int = 10,
    ) -> TradeProposal:
        proposal = TradeProposal(
            id=uuid.uuid4(),
            symbol=symbol,
            recommendation=recommendation,
            status=status,
            current_price=Decimal(str(entry_price)),
            entry_zone_min=Decimal(str(entry_price * 0.99)),
            entry_zone_max=Decimal(str(entry_price * 1.01)),
            suggested_price=Decimal(str(entry_price)),
            suggested_quantity=Decimal("0.01"),
            stop_loss_price=Decimal(str(stop_loss)),
            take_profit_prices=[{"target": take_profit, "pct": 100}],
            risk_reward_ratio=Decimal(str((take_profit - entry_price) / (entry_price - stop_loss))),
            confidence=Decimal(str(confidence)),
            supporting_reasons=["Strong uptrend", "RSI < 70", "Volume increasing"],
            risk_warnings=["High volatility"],
            critic_objections=[],
            environment=environment,
            version=1,
            expires_at=datetime.now(UTC) + timedelta(minutes=expires_in_minutes),
        )
        db.add(proposal)
        await db.flush()
        return proposal


class OrderFactory:
    """Create test orders."""

    @classmethod
    async def create(
        cls,
        db,
        proposal_id: str | None = None,
        symbol: str = "BTCUSDT",
        side: str = "BUY",
        order_type: str = "LIMIT",
        price: float = 50000.0,
        quantity: float = 0.01,
        status: str = "PENDING",
        environment: str = "PAPER",
    ) -> Order:
        order = Order(
            id=uuid.uuid4(),
            proposal_id=proposal_id,
            client_order_id=f"ACTA-{uuid.uuid4().hex[:8]}-1",
            symbol=symbol,
            side=side,
            order_type=order_type,
            price=Decimal(str(price)),
            quantity=Decimal(str(quantity)),
            filled_quantity=Decimal("0"),
            status=status,
            environment=environment,
        )
        db.add(order)
        await db.flush()
        return order


class WorkflowFactory:
    """Create test agent workflows."""

    @classmethod
    async def create(
        cls,
        db,
        symbol: str = "BTCUSDT",
        trigger_type: str = "MANUAL",
        status: str = "COMPLETED",
    ) -> AgentWorkflow:
        workflow = AgentWorkflow(
            id=uuid.uuid4(),
            symbol=symbol,
            trigger_type=trigger_type,
            status=status,
            started_at=datetime.now(UTC) - timedelta(seconds=30),
            completed_at=datetime.now(UTC),
            total_latency_ms=28500,
            total_input_tokens=5000,
            total_output_tokens=2000,
            total_estimated_cost=Decimal("0.008"),
        )
        db.add(workflow)
        await db.flush()
        return workflow
