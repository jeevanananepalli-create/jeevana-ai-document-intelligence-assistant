"""Async database engine and session management.

This module owns the connection to PostgreSQL. The application is async
end-to-end, so it uses SQLAlchemy's async engine with the `asyncpg` driver.

Connection pooling
------------------
Opening a PostgreSQL connection is expensive (a TCP handshake plus auth). A
*pool* keeps a set of connections open and hands them out to requests, returning
them to the pool when done instead of closing them. Without a pool, a burst of
traffic would open and close thousands of connections and likely exhaust the
database's connection limit. `pool_size` is the steady-state number kept open;
`max_overflow` is how many extra are allowed during spikes.

No tables are defined or created here in Phase 1 — this is purely the plumbing
that later phases and Alembic build on.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings


def _create_engine() -> AsyncEngine:
    """Build the async engine from settings, with an explicit connection pool."""
    settings = get_settings()
    return create_async_engine(
        settings.database_url,
        echo=settings.db_echo,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,  # transparently drop dead connections before use
    )


# A single engine per process. The engine manages the connection pool; it is
# created once and shared, never per-request.
engine: AsyncEngine = _create_engine()

# A factory that produces new AsyncSession objects bound to the engine.
# `expire_on_commit=False` keeps loaded objects usable after commit, which is
# the common preference for web request handlers.
SessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a database session per request.

    Usage in a route (later phases):

        async def handler(db: AsyncSession = Depends(get_db)): ...

    The session is opened when the request starts and guaranteed to close when
    it ends, even if the handler raises. Each request gets its own session, so
    sessions are never shared across concurrent requests.
    """
    async with SessionLocal() as session:
        yield session
