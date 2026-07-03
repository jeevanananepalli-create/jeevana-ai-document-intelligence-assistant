"""Integration tests for pgvector similarity search and query history.

Embeddings are handcrafted (no ML model needed): near-orthogonal unit vectors
give predictable cosine similarities, so ordering and scoping can be asserted
exactly against the real database and index.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.document_chunk import DocumentChunk
from app.domain.entities.query_record import QueryRecord
from app.infrastructure.database.models import DocumentModel, UserModel
from app.infrastructure.repositories.postgres_chunk import PostgresChunkRepository
from app.infrastructure.repositories.postgres_query_history import (
    PostgresQueryHistoryRepository,
)

_DIM = 384
_NOW = datetime(2026, 7, 2, tzinfo=UTC)


def _unit_vector(axis: int) -> list[float]:
    vector = [0.0] * _DIM
    vector[axis] = 1.0
    return vector


async def _seed_user_with_document(session: AsyncSession) -> tuple[UUID, UUID]:
    user = UserModel(id=uuid4(), email=f"{uuid4()}@example.com", password_hash="x")
    session.add(user)
    await session.flush()
    document = DocumentModel(
        id=uuid4(),
        user_id=user.id,
        original_filename="contract.pdf",
        file_type="pdf",
        file_size_bytes=1,
        storage_path="k",
        status="completed",
    )
    session.add(document)
    await session.flush()
    return user.id, document.id


def _chunk(document_id: UUID, index: int, content: str) -> DocumentChunk:
    return DocumentChunk(
        id=uuid4(), document_id=document_id, chunk_index=index, content=content, token_count=2
    )


async def test_search_orders_by_cosine_similarity(db_session: AsyncSession) -> None:
    user_id, document_id = await _seed_user_with_document(db_session)
    repo = PostgresChunkRepository(db_session)
    # Chunk 0 along axis 0, chunk 1 along axis 1.
    await repo.add_chunks(
        [_chunk(document_id, 0, "about payments"), _chunk(document_id, 1, "about weather")],
        [_unit_vector(0), _unit_vector(1)],
    )

    # A query vector leaning strongly towards axis 0 must rank chunk 0 first.
    query = [0.0] * _DIM
    query[0], query[1] = 0.9, 0.1
    results = await repo.search_similar(user_id, query, top_k=2)

    assert [r.content for r in results] == ["about payments", "about weather"]
    assert results[0].similarity > results[1].similarity
    assert results[0].similarity > 0.9  # nearly parallel vectors
    assert results[0].document_filename == "contract.pdf"


async def test_search_never_returns_other_users_chunks(db_session: AsyncSession) -> None:
    user_a, doc_a = await _seed_user_with_document(db_session)
    user_b, doc_b = await _seed_user_with_document(db_session)
    repo = PostgresChunkRepository(db_session)
    await repo.add_chunks([_chunk(doc_a, 0, "user A secret")], [_unit_vector(0)])
    await repo.add_chunks([_chunk(doc_b, 0, "user B data")], [_unit_vector(0)])

    results = await repo.search_similar(user_b, _unit_vector(0), top_k=10)

    assert [r.content for r in results] == ["user B data"]  # ownership enforced in SQL


async def test_search_respects_document_ids_filter(db_session: AsyncSession) -> None:
    user_id, doc_1 = await _seed_user_with_document(db_session)
    doc_2 = uuid4()
    db_session.add(
        DocumentModel(
            id=doc_2,
            user_id=user_id,
            original_filename="other.pdf",
            file_type="pdf",
            file_size_bytes=1,
            storage_path="k2",
            status="completed",
        )
    )
    await db_session.flush()
    repo = PostgresChunkRepository(db_session)
    await repo.add_chunks([_chunk(doc_1, 0, "in doc 1")], [_unit_vector(0)])
    await repo.add_chunks([_chunk(doc_2, 0, "in doc 2")], [_unit_vector(0)])

    results = await repo.search_similar(user_id, _unit_vector(0), top_k=10, document_ids=[doc_2])

    assert [r.content for r in results] == ["in doc 2"]


async def test_search_skips_chunks_without_embeddings(db_session: AsyncSession) -> None:
    from app.infrastructure.database.models import DocumentChunkModel

    user_id, document_id = await _seed_user_with_document(db_session)
    repo = PostgresChunkRepository(db_session)
    # One embedded chunk and one chunk whose embedding is still NULL.
    await repo.add_chunks([_chunk(document_id, 0, "embedded")], [_unit_vector(0)])
    db_session.add(
        DocumentChunkModel(
            id=uuid4(),
            document_id=document_id,
            chunk_index=1,
            content="not embedded yet",
            token_count=3,
        )
    )
    await db_session.flush()

    results = await repo.search_similar(user_id, _unit_vector(0), top_k=10)
    assert [r.content for r in results] == ["embedded"]


async def test_query_history_round_trip(db_session: AsyncSession) -> None:
    user_id, _ = await _seed_user_with_document(db_session)
    repo = PostgresQueryHistoryRepository(db_session)

    record = QueryRecord(
        id=uuid4(),
        user_id=user_id,
        question="What are the payment terms?",
        answer="30 days.",
        confidence=0.9,
        source_count=2,
        model_used="gpt-4o-mini",
        latency_ms=1234,
        created_at=_NOW,
    )
    await repo.add(record)

    assert await repo.count_for_user(user_id) == 1
    (stored,) = await repo.list_for_user(user_id)
    assert stored == record
