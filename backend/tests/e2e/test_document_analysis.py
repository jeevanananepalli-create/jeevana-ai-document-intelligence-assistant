"""End-to-end tests for the document analysis endpoint and detail embedding."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.domain.value_objects.document_analysis import DocumentAnalysis, ExtractedEntity
from tests.e2e.conftest import Ctx

DOCUMENTS_URL = "/api/v1/documents"

_ANALYSIS = DocumentAnalysis(
    summary="A service agreement between Acme Corp and Beta LLC.",
    document_type="contract",
    language="en",
    confidence=0.9,
    entities=(ExtractedEntity(name="Acme Corp", type="organization"),),
)


def _upload(client: TestClient) -> str:
    files = {"file": ("contract.pdf", b"%PDF-1.7 data", "application/pdf")}
    response = client.post(f"{DOCUMENTS_URL}/upload", files=files)
    assert response.status_code == 202
    return response.json()["id"]


async def _attach_analysis(ctx: Ctx, document_id: str) -> None:
    """Simulate the worker having produced analysis for the document."""
    # The E2E fixture uses the in-memory repository; find the owner then update.
    documents = await ctx.repository.list_for_user(_owner(ctx), limit=100)
    document = next(doc for doc in documents if str(doc.id) == document_id)
    await ctx.repository.update(document.with_analysis(_ANALYSIS, updated_at=datetime.now(UTC)))


def _owner(ctx: Ctx) -> UUID:
    # The placeholder auth attributes every request to the fixed dev user.
    return ctx.queue.calls[0][1]


async def test_analysis_endpoint_returns_analysis(ctx: Ctx) -> None:
    document_id = _upload(ctx.client)
    await _attach_analysis(ctx, document_id)

    response = ctx.client.get(f"{DOCUMENTS_URL}/{document_id}/analysis")

    assert response.status_code == 200
    body = response.json()
    assert body["summary"].startswith("A service agreement")
    assert body["document_type"] == "contract"
    assert body["language"] == "en"
    assert body["confidence"] == 0.9
    assert body["entities"] == [{"name": "Acme Corp", "type": "organization"}]


def test_analysis_404_when_not_yet_analyzed(ctx: Ctx) -> None:
    document_id = _upload(ctx.client)
    response = ctx.client.get(f"{DOCUMENTS_URL}/{document_id}/analysis")
    assert response.status_code == 404
    assert "not available" in response.json()["detail"].lower()


def test_analysis_404_when_document_missing(ctx: Ctx) -> None:
    response = ctx.client.get(f"{DOCUMENTS_URL}/{uuid4()}/analysis")
    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found"


async def test_detail_embeds_analysis_when_present(ctx: Ctx) -> None:
    document_id = _upload(ctx.client)

    before = ctx.client.get(f"{DOCUMENTS_URL}/{document_id}").json()
    assert before["analysis"] is None  # not analyzed yet

    await _attach_analysis(ctx, document_id)
    after = ctx.client.get(f"{DOCUMENTS_URL}/{document_id}").json()
    assert after["analysis"]["document_type"] == "contract"
