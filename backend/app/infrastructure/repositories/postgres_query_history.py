"""PostgreSQL implementation of the QueryHistoryRepository."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.query_record import QueryRecord
from app.infrastructure.database.models import QueryHistoryModel


def _to_domain(model: QueryHistoryModel) -> QueryRecord:
    return QueryRecord(
        id=model.id,
        user_id=model.user_id,
        question=model.question,
        answer=model.answer,
        confidence=model.confidence,
        source_count=model.source_count,
        model_used=model.model_used,
        latency_ms=model.latency_ms,
        created_at=model.created_at,
    )


class PostgresQueryHistoryRepository:
    """Query history persistence backed by PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, record: QueryRecord) -> QueryRecord:
        self._session.add(
            QueryHistoryModel(
                id=record.id,
                user_id=record.user_id,
                question=record.question,
                answer=record.answer,
                confidence=record.confidence,
                source_count=record.source_count,
                model_used=record.model_used,
                latency_ms=record.latency_ms,
                created_at=record.created_at,
            )
        )
        await self._session.flush()
        return record

    async def list_for_user(
        self, user_id: UUID, *, limit: int = 20, offset: int = 0
    ) -> list[QueryRecord]:
        stmt = (
            select(QueryHistoryModel)
            .where(QueryHistoryModel.user_id == user_id)
            .order_by(QueryHistoryModel.created_at.desc(), QueryHistoryModel.id.desc())
            .limit(limit)
            .offset(offset)
        )
        models = (await self._session.execute(stmt)).scalars().all()
        return [_to_domain(model) for model in models]

    async def count_for_user(self, user_id: UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(QueryHistoryModel)
            .where(QueryHistoryModel.user_id == user_id)
        )
        return (await self._session.execute(stmt)).scalar_one()
