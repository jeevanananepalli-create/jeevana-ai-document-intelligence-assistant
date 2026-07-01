"""Regression test for the Celery worker's per-task database engine.

Each Celery task runs its coroutine in a fresh event loop (`asyncio.run`). Async
DB connections are bound to the loop that created them, so a shared, pooled
engine breaks on the second task ("attached to a different loop"). `_worker_session`
builds a fresh NullPool engine per task to avoid this. This test proves two
sequential `asyncio.run` calls both succeed.
"""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import text

from app.workers.tasks import _worker_session


def test_worker_session_survives_multiple_event_loops() -> None:
    async def ping() -> int | None:
        async with _worker_session() as session:
            return (await session.execute(text("select 1"))).scalar()

    try:
        first = asyncio.run(ping())  # first event loop
    except Exception as exc:  # noqa: BLE001 - no database available => skip
        pytest.skip(f"PostgreSQL not available: {exc}")

    second = asyncio.run(ping())  # second, independent event loop
    assert first == 1
    assert second == 1
