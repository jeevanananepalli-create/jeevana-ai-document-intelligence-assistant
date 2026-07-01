"""Celery tasks: the document-processing pipeline entry point.

`process_document` is a thin wrapper that assembles the real adapters and runs
`ProcessDocumentUseCase`. All the interesting logic lives in the use case (and is
tested there); this module is about wiring, transactions, and retries.

Transaction/failure model:
- The pipeline runs in one session, committed on success.
- On failure we roll back any partial work, then record the `failed` status in a
  separate session so the failure is durably visible, and re-raise so Celery's
  retry policy (exponential backoff) kicks in.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID

from app.application.use_cases.process_document import ProcessDocumentUseCase
from app.core.config import get_settings
from app.domain.services.text_chunker import TextChunker
from app.infrastructure.database.session import SessionLocal
from app.infrastructure.external_services.embeddings import SentenceTransformerEmbedding
from app.infrastructure.repositories.postgres import PostgresDocumentRepository
from app.infrastructure.repositories.postgres_chunk import PostgresChunkRepository
from app.infrastructure.storage.local_storage import LocalFileStorage
from app.workers.celery_app import celery_app


@celery_app.task(
    name="process_document",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,  # exponential backoff between retries
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
)
def process_document(self: object, document_id: str, user_id: str) -> None:  # noqa: ARG001
    """Celery entry point. Runs the async pipeline to completion."""
    asyncio.run(_process(UUID(document_id), UUID(user_id)))


async def _process(document_id: UUID, user_id: UUID) -> None:
    settings = get_settings()
    async with SessionLocal() as session:
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
            await _record_failure(document_id, user_id, str(exc))
            raise


async def _record_failure(document_id: UUID, user_id: UUID, error: str) -> None:
    """Persist a `failed` status in its own transaction."""
    async with SessionLocal() as session:
        repository = PostgresDocumentRepository(session)
        document = await repository.get(document_id, user_id)
        if document is not None:
            await repository.update(document.mark_failed(updated_at=datetime.now(UTC), error=error))
            await session.commit()
