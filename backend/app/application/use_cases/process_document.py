"""Use case: process an uploaded document end to end.

This is the pipeline that the Celery worker runs:

    load record -> mark processing -> load file -> extract text -> chunk
    -> embed chunks -> store chunks -> mark completed   (or mark failed)

It depends only on domain ports, so the whole pipeline is unit-testable with
fakes — no Celery, Redis, database, or embedding model required to test the
orchestration logic. The concrete adapters are wired in the Celery task.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.domain.entities.document import Document
from app.domain.entities.document_chunk import DocumentChunk
from app.domain.exceptions import DocumentNotFoundError
from app.domain.interfaces.embeddings import EmbeddingPort
from app.domain.interfaces.extraction import ExtractionStrategy
from app.domain.interfaces.repositories import ChunkRepository, DocumentRepository
from app.domain.interfaces.storage import StoragePort
from app.domain.services.text_chunker import TextChunker
from app.domain.value_objects.document_status import DocumentStatus
from app.domain.value_objects.file_type import FileType
from app.infrastructure.extraction.factory import create_extraction_strategy


def _utcnow() -> datetime:
    return datetime.now(UTC)


class ProcessDocumentUseCase:
    """Run the extraction -> chunk -> embed -> store pipeline for one document."""

    def __init__(
        self,
        *,
        documents: DocumentRepository,
        chunks: ChunkRepository,
        storage: StoragePort,
        embedder: EmbeddingPort,
        chunker: TextChunker,
        strategy_factory: Callable[[FileType], ExtractionStrategy] = create_extraction_strategy,
        clock: Callable[[], datetime] = _utcnow,
    ) -> None:
        self._documents = documents
        self._chunks = chunks
        self._storage = storage
        self._embedder = embedder
        self._chunker = chunker
        self._strategy_factory = strategy_factory
        self._clock = clock

    async def execute(self, document_id: UUID, user_id: UUID) -> None:
        """Run the pipeline. Exceptions propagate to the caller (the Celery task),
        which owns transaction rollback, failure recording, and retries.
        """
        document = await self._documents.get(document_id, user_id)
        if document is None:
            raise DocumentNotFoundError(f"Document {document_id} not found for user {user_id}")

        document = await self._begin_processing(document)
        completed = await self._run_pipeline(document)
        await self._documents.update(completed)

    async def _begin_processing(self, document: Document) -> Document:
        # Guard makes retries idempotent: don't re-transition if already processing.
        if document.status is DocumentStatus.PROCESSING:
            return document
        document = document.with_status(DocumentStatus.PROCESSING, updated_at=self._clock())
        return await self._documents.update(document)

    async def _run_pipeline(self, document: Document) -> Document:
        content = await self._storage.load(document.storage_path)
        strategy = self._strategy_factory(document.file_type)
        result = strategy.extract(content)

        texts = self._chunker.chunk(result.text)
        chunks = [
            DocumentChunk(
                id=uuid4(),
                document_id=document.id,
                chunk_index=index,
                content=text,
                token_count=len(text.split()),
            )
            for index, text in enumerate(texts)
        ]

        embeddings = await self._embedder.embed_batch([c.content for c in chunks]) if chunks else []

        # Replace any existing chunks first, so re-processing is idempotent.
        await self._chunks.delete_for_document(document.id)
        if chunks:
            await self._chunks.add_chunks(chunks, embeddings)

        return document.mark_completed(
            updated_at=self._clock(),
            extracted_text=result.text,
            page_count=result.page_count,
        )
