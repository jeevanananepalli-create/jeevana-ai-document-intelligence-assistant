"""Tests for InMemoryDocumentRepository, including ownership enforcement."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.domain.entities.document import Document
from app.domain.value_objects.document_status import DocumentStatus
from app.domain.value_objects.file_type import FileType
from app.infrastructure.repositories.in_memory import InMemoryDocumentRepository

_NOW = datetime(2026, 6, 1, tzinfo=UTC)


def _make_document(*, user_id: UUID, created_at: datetime = _NOW) -> Document:
    return Document(
        id=uuid4(),
        user_id=user_id,
        original_filename="f.pdf",
        file_type=FileType.PDF,
        file_size_bytes=10,
        storage_path="key",
        status=DocumentStatus.UPLOADED,
        created_at=created_at,
        updated_at=created_at,
    )


async def test_add_then_get_by_owner() -> None:
    repo = InMemoryDocumentRepository()
    user_id = uuid4()
    document = await repo.add(_make_document(user_id=user_id))
    assert await repo.get(document.id, user_id) == document


async def test_get_enforces_ownership() -> None:
    repo = InMemoryDocumentRepository()
    document = await repo.add(_make_document(user_id=uuid4()))
    assert await repo.get(document.id, uuid4()) is None  # different user


async def test_list_for_user_returns_only_owned_newest_first() -> None:
    repo = InMemoryDocumentRepository()
    user_id = uuid4()
    older = await repo.add(_make_document(user_id=user_id, created_at=_NOW))
    newer = await repo.add(_make_document(user_id=user_id, created_at=_NOW + timedelta(days=1)))
    await repo.add(_make_document(user_id=uuid4()))  # someone else's

    result = await repo.list_for_user(user_id)
    assert [doc.id for doc in result] == [newer.id, older.id]


async def test_list_for_user_respects_limit_and_offset() -> None:
    repo = InMemoryDocumentRepository()
    user_id = uuid4()
    for index in range(5):
        await repo.add(_make_document(user_id=user_id, created_at=_NOW + timedelta(days=index)))

    page = await repo.list_for_user(user_id, limit=2, offset=1)
    assert len(page) == 2


async def test_update_replaces_document() -> None:
    repo = InMemoryDocumentRepository()
    user_id = uuid4()
    document = await repo.add(_make_document(user_id=user_id))
    moved = document.with_status(DocumentStatus.PROCESSING, updated_at=_NOW)

    await repo.update(moved)
    assert (await repo.get(document.id, user_id)).status is DocumentStatus.PROCESSING  # type: ignore[union-attr]


async def test_delete_by_owner_and_non_owner() -> None:
    repo = InMemoryDocumentRepository()
    user_id = uuid4()
    document = await repo.add(_make_document(user_id=user_id))

    assert await repo.delete(document.id, uuid4()) is False  # not the owner
    assert await repo.delete(document.id, user_id) is True
    assert await repo.delete(document.id, user_id) is False  # already gone


async def test_count_for_user_counts_only_owned() -> None:
    repo = InMemoryDocumentRepository()
    user_id = uuid4()
    await repo.add(_make_document(user_id=user_id))
    await repo.add(_make_document(user_id=user_id))
    await repo.add(_make_document(user_id=uuid4()))  # someone else's

    assert await repo.count_for_user(user_id) == 2
