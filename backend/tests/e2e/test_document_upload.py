"""End-to-end tests for POST /api/v1/documents/upload via the HTTP stack."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient

from app.api.deps import get_processing_queue, get_upload_document_use_case
from app.application.use_cases.upload_document import UploadDocumentUseCase
from app.infrastructure.repositories.in_memory import InMemoryDocumentRepository
from app.infrastructure.storage.local_storage import LocalFileStorage
from app.main import create_app
from tests.e2e.conftest import Ctx, FakeQueue

UPLOAD_URL = "/api/v1/documents/upload"


def test_upload_pdf_returns_202_and_enqueues_processing(ctx: Ctx) -> None:
    files = {"file": ("contract.pdf", b"%PDF-1.7 fake", "application/pdf")}
    response = ctx.client.post(UPLOAD_URL, files=files)

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "uploaded"
    assert body["file_type"] == "pdf"
    assert body["original_filename"] == "contract.pdf"
    assert body["file_size_bytes"] == len(b"%PDF-1.7 fake")
    document_id = UUID(body["id"])
    # The document was handed to the processing queue exactly once.
    assert len(ctx.queue.calls) == 1
    assert ctx.queue.calls[0][0] == document_id


def test_upload_unsupported_type_returns_415(ctx: Ctx) -> None:
    files = {"file": ("archive.zip", b"PK\x03\x04", "application/zip")}
    assert ctx.client.post(UPLOAD_URL, files=files).status_code == 415
    assert ctx.queue.calls == []  # nothing queued on rejection


def test_upload_empty_file_returns_422(ctx: Ctx) -> None:
    files = {"file": ("empty.pdf", b"", "application/pdf")}
    assert ctx.client.post(UPLOAD_URL, files=files).status_code == 422


def test_upload_too_large_returns_413(tmp_path: Path) -> None:
    # Override the use case with a tiny size limit so we can trigger 413 without
    # sending a 50 MB payload.
    app = create_app()
    repository = InMemoryDocumentRepository()

    def _tiny_use_case() -> UploadDocumentUseCase:
        return UploadDocumentUseCase(
            storage=LocalFileStorage(tmp_path),
            repository=repository,
            max_file_size_bytes=8,
        )

    app.dependency_overrides[get_upload_document_use_case] = _tiny_use_case
    app.dependency_overrides[get_processing_queue] = FakeQueue
    with TestClient(app) as client:
        files = {"file": ("big.pdf", b"x" * 9, "application/pdf")}
        assert client.post(UPLOAD_URL, files=files).status_code == 413
    app.dependency_overrides.clear()
