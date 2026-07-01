"""Celery tasks: the document-processing pipeline entry point.

`process_document` is a thin wrapper that assembles the real adapters and runs
`ProcessDocumentUseCase`. All the interesting logic lives in the use case (and is
tested there); this module is about wiring, transactions, and retries.

Event-loop / engine note (important):
Each task runs its coroutine via `asyncio.run`, which creates a *new* event loop
per task. Async database connections are bound to the loop that created them, so
a process-wide pooled engine would hand out connections from a dead loop on the
next task. We therefore build a fresh engine with `NullPool` per task and dispose
it afterwards — the correct pattern for async SQLAlchemy under Celery's prefork.

Transaction/failure model:
- The pipeline runs in one session, committed on success.
- On failure we roll back partial work and re-raise so Celery's retry policy
  (exponential backoff) kicks in. We only persist the `failed` status on the
  *final* attempt, so a document is not shown as failed while retries remain.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import NullPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.application.use_cases.process_document import ProcessDocumentUseCase
from app.core.config import get_settings
from app.domain.services.text_chunker import TextChunker
from app.infrastructure.external_services.embeddings import SentenceTransformerEmbedding
from app.infrastructure.repositories.postgres import PostgresDocumentRepository
from app.infrastructure.repositories.postgres_chunk import PostgresChunkRepository
from app.infrastructure.storage.local_storage import LocalFileStorage
from app.workers.celery_app import celery_app


@asynccontextmanager
async def _worker_session() -> AsyncIterator[AsyncSession]:
    """Yield a session from a fresh, non-pooled engine bound to the current loop."""
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            yield session
    finally:
        await engine.dispose()


@celery_app.task(
    name="process_document",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,  # exponential backoff between retries
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
)
def process_document(self: Any, document_id: str, user_id: str) -> None:
    """Celery entry point. Runs the async pipeline to completion."""
    is_final_attempt = self.request.retries >= self.max_retries
    asyncio.run(_process(UUID(document_id), UUID(user_id), record_failure=is_final_attempt))


async def _process(document_id: UUID, user_id: UUID, *, record_failure: bool) -> None:
    settings = get_settings()
    async with _worker_session() as session:
        use_case = ProcessDocumentUseCase(
            documents=PostgresDocumentRepository(session),
            chunks=PostgresChunkRepository(session),
            storage=LocalFileStorage(settings.storage_path),
            embedder=SentenceTransformerEmbedding(
                settings.embedding_model, settings.embedding_dimension
            ),
            chunker=TextChunker(),
        )
        try:
            await use_case.execute(document_id, user_id)
            await session.commit()
        except Exception as exc:
            await session.rollback()
            # Only mark failed once retries are exhausted, so the document is not
            # flapping to "failed" while transient errors are still being retried.
            if record_failure:
                await _record_failure(document_id, user_id, str(exc))
            raise


async def _record_failure(document_id: UUID, user_id: UUID, error: str) -> None:
    """Persist a `failed` status in its own transaction."""
    async with _worker_session() as session:
        repository = PostgresDocumentRepository(session)
        document = await repository.get(document_id, user_id)
        if document is not None:
            await repository.update(document.mark_failed(updated_at=datetime.now(UTC), error=error))
            await session.commit()
