"""Feature repository — CRUD operations for technical features."""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.feature import TechnicalFeature

logger = structlog.get_logger(__name__)


class FeatureRepository:
    """Repository for TechnicalFeature records."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def save(
        self,
        symbol: str,
        timeframe: str,
        features: dict,
        computed_at: datetime | None = None,
        version: str = "v1",
    ) -> TechnicalFeature:
        """Insert a new feature record."""
        if computed_at is None:
            computed_at = datetime.now(UTC)

        record = TechnicalFeature(
            symbol=symbol,
            timeframe=timeframe,
            computed_at=computed_at,
            features=features,
            version=version,
        )
        self.db.add(record)
        await self.db.flush()
        logger.debug("feature_saved", symbol=symbol, timeframe=timeframe, version=version)
        return record

    async def get_latest(self, symbol: str, timeframe: str) -> TechnicalFeature | None:
        """Get the most recent feature record for a symbol/timeframe."""
        result = await self.db.execute(
            select(TechnicalFeature)
            .where(
                TechnicalFeature.symbol == symbol,
                TechnicalFeature.timeframe == timeframe,
            )
            .order_by(TechnicalFeature.computed_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_history(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 20,
    ) -> list[TechnicalFeature]:
        """Get recent feature records for trend analysis."""
        result = await self.db.execute(
            select(TechnicalFeature)
            .where(
                TechnicalFeature.symbol == symbol,
                TechnicalFeature.timeframe == timeframe,
            )
            .order_by(TechnicalFeature.computed_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def delete_old(self, symbol: str, before: datetime) -> int:
        """Remove old feature records to keep table size manageable."""
        from sqlalchemy import delete

        result = await self.db.execute(
            delete(TechnicalFeature).where(
                TechnicalFeature.symbol == symbol,
                TechnicalFeature.computed_at < before,
            )
        )
        await self.db.commit()
        return result.rowcount or 0
