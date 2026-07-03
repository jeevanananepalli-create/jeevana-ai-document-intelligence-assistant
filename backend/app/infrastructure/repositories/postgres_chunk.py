"""PostgreSQL implementation of the ChunkRepository.

Persists a document's text chunks together with their vector embeddings into the
`document_chunks` table (the embedding goes into the pgvector column), and runs
the cosine-similarity search that powers semantic search and RAG retrieval.
Like the document repository, write methods only stage changes; the request/task
boundary commits.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.document_chunk import DocumentChunk
from app.domain.value_objects.search import ChunkSearchResult
from app.infrastructure.database.models import DocumentChunkModel, DocumentModel


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

    async def search_similar(
        self,
        user_id: UUID,
        query_embedding: list[float],
        *,
        top_k: int = 5,
        document_ids: list[UUID] | None = None,
    ) -> list[ChunkSearchResult]:
        """Nearest-neighbour search by cosine distance, scoped to the user.

        pgvector's `<=>` operator (exposed as `.cosine_distance`) returns
        distance in [0, 2]; similarity is `1 - distance`. Ordering by the same
        expression lets PostgreSQL use the IVFFlat index built in migration 0001.
        Ownership is enforced in the JOIN: only chunks of the user's documents
        are ever considered.
        """
        distance = DocumentChunkModel.embedding.cosine_distance(query_embedding)
        stmt = (
            select(
                DocumentChunkModel.id,
                DocumentChunkModel.document_id,
                DocumentModel.original_filename,
                DocumentChunkModel.content,
                DocumentChunkModel.chunk_index,
                DocumentChunkModel.page_number,
                distance.label("distance"),
            )
            .join(DocumentModel, DocumentChunkModel.document_id == DocumentModel.id)
            .where(
                DocumentModel.user_id == user_id,
                DocumentChunkModel.embedding.is_not(None),
            )
            .order_by(distance)
            .limit(top_k)
        )
        if document_ids:
            stmt = stmt.where(DocumentChunkModel.document_id.in_(document_ids))

        rows = (await self._session.execute(stmt)).all()
        return [
            ChunkSearchResult(
                chunk_id=row.id,
                document_id=row.document_id,
                document_filename=row.original_filename,
                content=row.content,
                similarity=1.0 - row.distance,
                chunk_index=row.chunk_index,
                page_number=row.page_number,
            )
            for row in rows
        ]
