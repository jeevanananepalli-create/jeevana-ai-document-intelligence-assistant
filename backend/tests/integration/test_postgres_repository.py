"""Integration tests for PostgresDocumentRepository against real PostgreSQL.

These verify the ORM mapping and queries — the same behaviours the in-memory
repository tests cover, but through actual SQL — plus ownership enforcement.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.document import Document
from app.domain.value_objects.document_status import DocumentStatus
from app.domain.value_objects.file_type import FileType
from app.infrastructure.database.models import UserModel
from app.infrastructure.repositories.postgres import PostgresDocumentRepository

_NOW = datetime(2026, 7, 1, tzinfo=UTC)


async def _seed_user(session: AsyncSession) -> UUID:
    """Insert a user row so documents satisfy their foreign key."""
    user = UserModel(id=uuid4(), email=f"{uuid4()}@example.com", password_hash="x")
    session.add(user)
    await session.flush()
    return user.id


def _make_document(*, user_id: UUID, created_at: datetime = _NOW) -> Document:
    return Document(
        id=uuid4(),
        user_id=user_id,
        original_filename="contract.pdf",
        file_type=FileType.PDF,
        file_size_bytes=2048,
        storage_path="abc.pdf",
        status=DocumentStatus.UPLOADED,
        created_at=created_at,
        updated_at=created_at,
    )


async def test_add_then_get_round_trips(db_session: AsyncSession) -> None:
    repo = PostgresDocumentRepository(db_session)
    user_id = await _seed_user(db_session)

    document = await repo.add(_make_document(user_id=user_id))
    fetched = await repo.get(document.id, user_id)

    assert fetched is not None
    assert fetched.id == document.id
    assert fetched.file_type is FileType.PDF
    assert fetched.status is DocumentStatus.UPLOADED


async def test_get_enforces_ownership(db_session: AsyncSession) -> None:
    repo = PostgresDocumentRepository(db_session)
    user_id = await _seed_user(db_session)
    document = await repo.add(_make_document(user_id=user_id))

    other_user = await _seed_user(db_session)
    assert await repo.get(document.id, other_user) is None


async def test_list_for_user_orders_newest_first(db_session: AsyncSession) -> None:
    repo = PostgresDocumentRepository(db_session)
    user_id = await _seed_user(db_session)
    older = await repo.add(_make_document(user_id=user_id, created_at=_NOW))
    newer = await repo.add(_make_document(user_id=user_id, created_at=_NOW + timedelta(days=1)))

    result = await repo.list_for_user(user_id)
    assert [doc.id for doc in result] == [newer.id, older.id]


async def test_update_persists_status_change(db_session: AsyncSession) -> None:
    repo = PostgresDocumentRepository(db_session)
    user_id = await _seed_user(db_session)
    document = await repo.add(_make_document(user_id=user_id))

    moved = document.with_status(DocumentStatus.PROCESSING, updated_at=_NOW)
    await repo.update(moved)

    refetched = await repo.get(document.id, user_id)
    assert refetched is not None
    assert refetched.status is DocumentStatus.PROCESSING


async def test_count_for_user(db_session: AsyncSession) -> None:
    repo = PostgresDocumentRepository(db_session)
    user_id = await _seed_user(db_session)
    await repo.add(_make_document(user_id=user_id))
    await repo.add(_make_document(user_id=user_id))

    other_user = await _seed_user(db_session)
    await repo.add(_make_document(user_id=other_user))

    assert await repo.count_for_user(user_id) == 2
    assert await repo.count_for_user(other_user) == 1


async def test_update_missing_document_is_noop(db_session: AsyncSession) -> None:
    repo = PostgresDocumentRepository(db_session)
    ghost = _make_document(user_id=uuid4())  # never persisted
    assert await repo.update(ghost) == ghost


async def test_delete_removes_only_owned_document(db_session: AsyncSession) -> None:
    repo = PostgresDocumentRepository(db_session)
    user_id = await _seed_user(db_session)
    document = await repo.add(_make_document(user_id=user_id))

    other_user = await _seed_user(db_session)
    assert await repo.delete(document.id, other_user) is False
    assert await repo.delete(document.id, user_id) is True
    assert await repo.get(document.id, user_id) is None
