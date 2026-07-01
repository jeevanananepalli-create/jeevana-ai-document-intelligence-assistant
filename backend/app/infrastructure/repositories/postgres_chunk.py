"""PostgreSQL implementation of the ChunkRepository.

Persists a document's text chunks together with their vector embeddings into the
`document_chunks` table (the embedding goes into the pgvector column). Like the
document repository, it only stages changes; the request/task boundary commits.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.document_chunk import DocumentChunk
from app.infrastructure.database.models import DocumentChunkModel


class PostgresChunkRepository:
    """A ChunkRepository backed by PostgreSQL + pgvector."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_chunks(self, chunks: list[DocumentChunk], embeddings: list[list[float]]) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must be the same length")

        self._session.add_all(
            DocumentChunkModel(
                id=chunk.id,
                document_id=chunk.document_id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                token_count=chunk.token_count,
                page_number=chunk.page_number,
                embedding=embedding,
            )
            for chunk, embedding in zip(chunks, embeddings, strict=True)
        )
        await self._session.flush()

    async def delete_for_document(self, document_id: UUID) -> None:
        await self._session.execute(
            delete(DocumentChunkModel).where(DocumentChunkModel.document_id == document_id)
        )
