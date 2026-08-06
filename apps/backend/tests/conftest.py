"""Test configuration and fixtures."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncGenerator

# ── Override env BEFORE importing app ──────────────────────────────
# The app reads DATABASE_URL at import time. In CI, DATABASE_URL points to
# a PostgreSQL test DB that may not exist yet. Since our tests use SQLite
# via dependency injection (db_session fixture), we force-override DATABASE_URL
# to prevent app startup from failing when connecting to a non-existent PG DB.
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.database.base import Base  # noqa: E402
from app.database.session import get_db_session  # noqa: E402
from app.main import app  # noqa: E402

# Always use SQLite for test fixtures (fast, no external dependency)
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session with a fresh schema for each test."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create a test HTTP client with database dependency override."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
