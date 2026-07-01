"""Tests for UploadDocumentUseCase.

These exercise the orchestration with a fake StoragePort and the real in-memory
repository, so no filesystem, database, or HTTP is involved.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.application.use_cases.upload_document import UploadDocumentUseCase
from app.domain.exceptions import (
    EmptyFileError,
    FileTooLargeError,
    UnsupportedFileTypeError,
)
from app.domain.value_objects.document_status import DocumentStatus
from app.domain.value_objects.file_type import FileType
from app.infrastructure.repositories.in_memory import InMemoryDocumentRepository

_FIXED_NOW = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)


class _FakeStorage:
    """A StoragePort test double that keeps bytes in a dict."""

    def __init__(self) -> None:
        self.saved: dict[str, bytes] = {}

    async def save(self, content: bytes, *, filename: str) -> str:
        key = f"stored-{len(self.saved)}-{filename}"
        self.saved[key] = content
        return key

    async def load(self, storage_path: str) -> bytes:
        return self.saved[storage_path]

    async def delete(self, storage_path: str) -> None:
        self.saved.pop(storage_path, None)


def _make_use_case(
    *, storage: _FakeStorage, repository: InMemoryDocumentRepository, max_bytes: int = 1_000_000
) -> UploadDocumentUseCase:
    return UploadDocumentUseCase(
        storage=storage,
        repository=repository,
        max_file_size_bytes=max_bytes,
        clock=lambda: _FIXED_NOW,
    )


async def test_upload_happy_path_persists_document() -> None:
    storage = _FakeStorage()
    repository = InMemoryDocumentRepository()
    use_case = _make_use_case(storage=storage, repository=repository)
    user_id = uuid4()

    document = await use_case.execute(
        user_id=user_id,
        original_filename="contract.pdf",
        content=b"%PDF-1.7 fake pdf bytes",
        content_type="application/pdf",
    )

    assert document.status is DocumentStatus.UPLOADED
    assert document.file_type is FileType.PDF
    assert document.file_size_bytes == len(b"%PDF-1.7 fake pdf bytes")
    assert document.created_at == _FIXED_NOW
    # Bytes were stored and the document is retrievable by its owner.
    assert storage.saved[document.storage_path] == b"%PDF-1.7 fake pdf bytes"
    assert await repository.get(document.id, user_id) is not None


async def test_upload_rejects_unsupported_type_before_storing() -> None:
    storage = _FakeStorage()
    use_case = _make_use_case(storage=storage, repository=InMemoryDocumentRepository())

    with pytest.raises(UnsupportedFileTypeError):
        await use_case.execute(
            user_id=uuid4(),
            original_filename="archive.zip",
            content=b"PK\x03\x04",
            content_type="application/zip",
        )
    assert storage.saved == {}  # nothing was stored


async def test_upload_rejects_empty_file() -> None:
    use_case = _make_use_case(storage=_FakeStorage(), repository=InMemoryDocumentRepository())
    with pytest.raises(EmptyFileError):
        await use_case.execute(
            user_id=uuid4(),
            original_filename="empty.pdf",
            content=b"",
            content_type="application/pdf",
        )


async def test_upload_rejects_file_over_size_limit() -> None:
    storage = _FakeStorage()
    use_case = _make_use_case(
        storage=storage, repository=InMemoryDocumentRepository(), max_bytes=10
    )
    with pytest.raises(FileTooLargeError):
        await use_case.execute(
            user_id=uuid4(),
            original_filename="big.pdf",
            content=b"x" * 11,
            content_type="application/pdf",
        )
    assert storage.saved == {}  # rejected before storing
