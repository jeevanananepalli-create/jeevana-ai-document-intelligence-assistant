"""Integration tests for PostgresChunkRepository against real PostgreSQL + pgvector.

Verifies chunks are written with their embedding vectors into the pgvector
column, and that delete_for_document clears them (the idempotency primitive).
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.document_chunk import DocumentChunk
from app.infrastructure.database.models import DocumentChunkModel, DocumentModel, UserModel
from app.infrastructure.repositories.postgres_chunk import PostgresChunkRepository

_DIM = 384


async def _seed_document(session: AsyncSession) -> UUID:
    user = UserModel(id=uuid4(), email=f"{uuid4()}@example.com", password_hash="x")
    session.add(user)
    await session.flush()
    document = DocumentModel(
        id=uuid4(),
        user_id=user.id,
        original_filename="d.pdf",
        file_type="pdf",
        file_size_bytes=1,
        storage_path="k",
        status="processing",
    )
    session.add(document)
    await session.flush()
    return document.id


async def _count_chunks(session: AsyncSession, document_id: UUID) -> int:
    return await session.scalar(
        select(func.count())
        .select_from(DocumentChunkModel)
        .where(DocumentChunkModel.document_id == document_id)
    )


async def test_add_chunks_persists_content_and_embeddings(db_session: AsyncSession) -> None:
    document_id = await _seed_document(db_session)
    repo = PostgresChunkRepository(db_session)

    chunks = [
        DocumentChunk(
            id=uuid4(), document_id=document_id, chunk_index=i, content=f"chunk {i}", token_count=2
        )
        for i in range(3)
    ]
    embeddings = [[0.1 * i] * _DIM for i in range(3)]
    await repo.add_chunks(chunks, embeddings)

    assert await _count_chunks(db_session, document_id) == 3
    stored = await db_session.scalar(
        select(DocumentChunkModel).where(DocumentChunkModel.chunk_index == 0)
    )
    assert stored is not None
    assert len(stored.embedding) == _DIM  # vector round-tripped through pgvector


async def test_delete_for_document_clears_chunks(db_session: AsyncSession) -> None:
    document_id = await _seed_document(db_session)
    repo = PostgresChunkRepository(db_session)
    await repo.add_chunks(
        [
            DocumentChunk(
                id=uuid4(), document_id=document_id, chunk_index=0, content="c", token_count=1
            )
        ],
        [[0.0] * _DIM],
    )
    assert await _count_chunks(db_session, document_id) == 1

    await repo.delete_for_document(document_id)
    assert await _count_chunks(db_session, document_id) == 0


async def test_add_chunks_rejects_length_mismatch(db_session: AsyncSession) -> None:
    repo = PostgresChunkRepository(db_session)
    chunk = DocumentChunk(
        id=uuid4(), document_id=uuid4(), chunk_index=0, content="c", token_count=1
    )
    with pytest.raises(ValueError, match="same length"):
        await repo.add_chunks([chunk], [])
