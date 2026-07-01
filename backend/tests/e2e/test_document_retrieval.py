"""End-to-end tests for the document read/delete endpoints."""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from tests.e2e.conftest import Ctx

DOCUMENTS_URL = "/api/v1/documents"


def _upload(client: TestClient, name: str = "doc.pdf") -> str:
    files = {"file": (name, b"%PDF-1.7 data", "application/pdf")}
    response = client.post(f"{DOCUMENTS_URL}/upload", files=files)
    assert response.status_code == 202
    return response.json()["id"]


def test_list_returns_uploaded_documents(ctx: Ctx) -> None:
    document_id = _upload(ctx.client)
    response = ctx.client.get(DOCUMENTS_URL)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["has_next"] is False
    assert body["items"][0]["id"] == document_id
    assert body["items"][0]["status"] == "uploaded"


def test_list_paginates(ctx: Ctx) -> None:
    for index in range(3):
        _upload(ctx.client, name=f"doc{index}.pdf")

    first = ctx.client.get(DOCUMENTS_URL, params={"page": 1, "limit": 2}).json()
    assert len(first["items"]) == 2
    assert first["total"] == 3
    assert first["has_next"] is True

    second = ctx.client.get(DOCUMENTS_URL, params={"page": 2, "limit": 2}).json()
    assert len(second["items"]) == 1
    assert second["has_next"] is False


def test_get_document_detail(ctx: Ctx) -> None:
    document_id = _upload(ctx.client)
    response = ctx.client.get(f"{DOCUMENTS_URL}/{document_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == document_id
    assert body["file_type"] == "pdf"
    assert body["extracted_text"] is None  # not processed yet


def test_get_missing_document_returns_404(ctx: Ctx) -> None:
    assert ctx.client.get(f"{DOCUMENTS_URL}/{uuid4()}").status_code == 404


def test_get_status(ctx: Ctx) -> None:
    document_id = _upload(ctx.client)
    response = ctx.client.get(f"{DOCUMENTS_URL}/{document_id}/status")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == document_id
    assert body["status"] == "uploaded"
    assert body["processing_error"] is None


def test_delete_document_then_404(ctx: Ctx) -> None:
    document_id = _upload(ctx.client)

    delete_response = ctx.client.delete(f"{DOCUMENTS_URL}/{document_id}")
    assert delete_response.status_code == 200
    assert delete_response.json()["message"] == "Document deleted successfully"

    # It is gone afterwards.
    assert ctx.client.get(f"{DOCUMENTS_URL}/{document_id}").status_code == 404


def test_delete_missing_document_returns_404(ctx: Ctx) -> None:
    assert ctx.client.delete(f"{DOCUMENTS_URL}/{uuid4()}").status_code == 404
