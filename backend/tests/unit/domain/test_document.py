"""Tests for the Document entity: immutability and status transitions."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.domain.entities.document import Document
from app.domain.exceptions import InvalidStatusTransitionError
from app.domain.value_objects.document_status import DocumentStatus
from app.domain.value_objects.file_type import FileType

_T0 = datetime(2026, 1, 1, tzinfo=UTC)
_T1 = datetime(2026, 1, 2, tzinfo=UTC)


def _make_document(status: DocumentStatus = DocumentStatus.UPLOADED) -> Document:
    return Document(
        id=uuid4(),
        user_id=uuid4(),
        original_filename="contract.pdf",
        file_type=FileType.PDF,
        file_size_bytes=1024,
        storage_path="documents/abc.pdf",
        status=status,
        created_at=_T0,
        updated_at=_T0,
    )


def test_document_is_immutable() -> None:
    """The entity is frozen: attributes cannot be reassigned in place."""
    document = _make_document()
    with pytest.raises(dataclasses.FrozenInstanceError):
        document.status = DocumentStatus.COMPLETED  # type: ignore[misc]


def test_with_status_returns_a_new_updated_document() -> None:
    document = _make_document(DocumentStatus.UPLOADED)
    updated = document.with_status(DocumentStatus.PROCESSING, updated_at=_T1)

    assert updated.status is DocumentStatus.PROCESSING
    assert updated.updated_at == _T1
    assert updated.id == document.id  # same identity


def test_with_status_does_not_mutate_the_original() -> None:
    document = _make_document(DocumentStatus.UPLOADED)
    document.with_status(DocumentStatus.PROCESSING, updated_at=_T1)
    assert document.status is DocumentStatus.UPLOADED  # original untouched


def test_with_status_records_processing_error() -> None:
    document = _make_document(DocumentStatus.PROCESSING)
    failed = document.with_status(
        DocumentStatus.FAILED, updated_at=_T1, processing_error="OCR failed"
    )
    assert failed.status is DocumentStatus.FAILED
    assert failed.processing_error == "OCR failed"


def test_with_status_rejects_illegal_transition() -> None:
    document = _make_document(DocumentStatus.UPLOADED)
    with pytest.raises(InvalidStatusTransitionError):
        document.with_status(DocumentStatus.COMPLETED, updated_at=_T1)


def test_mark_completed_carries_extraction_results() -> None:
    document = _make_document(DocumentStatus.PROCESSING)
    completed = document.mark_completed(
        updated_at=_T1, extracted_text="the full text", page_count=7
    )
    assert completed.status is DocumentStatus.COMPLETED
    assert completed.extracted_text == "the full text"
    assert completed.page_count == 7
    assert completed.processing_error is None


def test_mark_completed_rejects_illegal_transition() -> None:
    document = _make_document(DocumentStatus.UPLOADED)  # cannot complete directly
    with pytest.raises(InvalidStatusTransitionError):
        document.mark_completed(updated_at=_T1, extracted_text="x", page_count=1)


def test_mark_failed_records_error() -> None:
    document = _make_document(DocumentStatus.PROCESSING)
    failed = document.mark_failed(updated_at=_T1, error="embedding failed")
    assert failed.status is DocumentStatus.FAILED
    assert failed.processing_error == "embedding failed"


def test_mark_failed_allowed_directly_from_uploaded() -> None:
    document = _make_document(DocumentStatus.UPLOADED)
    failed = document.mark_failed(updated_at=_T1, error="could not read file")
    assert failed.status is DocumentStatus.FAILED
