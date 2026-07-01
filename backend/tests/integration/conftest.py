"""Fixtures for integration tests that need a real PostgreSQL + pgvector.

The `db_session` fixture builds the schema on a real database and yields a
session. If no database is reachable (e.g. a local run without `docker compose
up db`), the dependent tests are skipped rather than failed, so the default
`pytest` run stays green without infrastructure. CI provides a Postgres service,
so these run there.

Connection details come from the same Settings the app uses (DATABASE_URL).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import NullPool, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.infrastructure.database import models  # noqa: F401  (register tables)
from app.infrastructure.database.base import Base


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
    except Exception as exc:  # noqa: BLE001 - any connect/setup failure => skip
        await engine.dispose()
        pytest.skip(f"PostgreSQL not available for integration tests: {exc}")

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
