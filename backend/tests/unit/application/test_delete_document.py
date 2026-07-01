"""Tests for DeleteDocumentUseCase."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.application.use_cases.delete_document import DeleteDocumentUseCase
from app.domain.entities.document import Document
from app.domain.value_objects.document_status import DocumentStatus
from app.domain.value_objects.file_type import FileType
from app.infrastructure.repositories.in_memory import InMemoryDocumentRepository

_NOW = datetime(2026, 7, 1, tzinfo=UTC)


class _FakeStorage:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    async def delete(self, storage_path: str) -> None:
        self.deleted.append(storage_path)


def _make_document(*, user_id: UUID) -> Document:
    return Document(
        id=uuid4(),
        user_id=user_id,
        original_filename="f.pdf",
        file_type=FileType.PDF,
        file_size_bytes=10,
        storage_path="stored-key.pdf",
        status=DocumentStatus.UPLOADED,
        created_at=_NOW,
        updated_at=_NOW,
    )


async def test_delete_removes_record_and_file() -> None:
    repository = InMemoryDocumentRepository()
    storage = _FakeStorage()
    user_id = uuid4()
    document = await repository.add(_make_document(user_id=user_id))

    use_case = DeleteDocumentUseCase(repository=repository, storage=storage)  # type: ignore[arg-type]
    result = await use_case.execute(document.id, user_id)

    assert result is True
    assert await repository.get(document.id, user_id) is None
    assert storage.deleted == ["stored-key.pdf"]


async def test_delete_missing_returns_false_and_touches_nothing() -> None:
    storage = _FakeStorage()
    use_case = DeleteDocumentUseCase(
        repository=InMemoryDocumentRepository(),  # empty
        storage=storage,  # type: ignore[arg-type]
    )
    assert await use_case.execute(uuid4(), uuid4()) is False
    assert storage.deleted == []


async def test_delete_enforces_ownership() -> None:
    repository = InMemoryDocumentRepository()
    storage = _FakeStorage()
    document = await repository.add(_make_document(user_id=uuid4()))

    use_case = DeleteDocumentUseCase(repository=repository, storage=storage)  # type: ignore[arg-type]
    assert await use_case.execute(document.id, uuid4()) is False  # different user
    assert storage.deleted == []
