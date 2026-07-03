"""End-to-end tests for the search and Q&A endpoints.

Embedder, chunk repository, LLM, and history are overridden with fakes, so
these exercise the full HTTP layer (validation, serialization, status codes)
without any model, database, or network.
"""

from __future__ import annotations

from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.deps import (
    get_chunk_repository,
    get_embedder,
    get_llm,
    get_query_history_repository,
)
from app.domain.value_objects.search import ChunkSearchResult, RagAnswer
from app.infrastructure.repositories.in_memory import InMemoryQueryHistoryRepository
from app.main import create_app

_DIM = 8

_CHUNK = ChunkSearchResult(
    chunk_id=uuid4(),
    document_id=uuid4(),
    document_filename="contract.pdf",
    content="Payment shall be made within 30 calendar days of invoice.",
    similarity=0.87,
    chunk_index=4,
    page_number=5,
)


class _FakeEmbedder:
    @property
    def dimension(self) -> int:
        return _DIM

    async def embed_text(self, text: str) -> list[float]:
        return [0.1] * _DIM

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * _DIM for _ in texts]


class _FakeChunks:
    def __init__(self, results: list[ChunkSearchResult]) -> None:
        self._results = results

    async def search_similar(
        self,
        user_id: UUID,
        query_embedding: list[float],
        *,
        top_k: int = 5,
        document_ids: list[UUID] | None = None,
    ) -> list[ChunkSearchResult]:
        return self._results[:top_k]


class _FakeLLM:
    async def generate_answer(self, question: str, contexts: list[str]) -> RagAnswer:
        return RagAnswer(
            answer="Payment is due within 30 calendar days.",
            confidence=0.9,
            used_source_indices=(0,),
        )


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app()
    history = InMemoryQueryHistoryRepository()
    app.dependency_overrides[get_embedder] = _FakeEmbedder
    app.dependency_overrides[get_chunk_repository] = lambda: _FakeChunks([_CHUNK])
    app.dependency_overrides[get_llm] = _FakeLLM
    app.dependency_overrides[get_query_history_repository] = lambda: history
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_search_returns_ranked_chunks(client: TestClient) -> None:
    response = client.post("/api/v1/search", json={"query": "payment terms"})

    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "payment terms"
    assert body["total_results"] == 1
    result = body["results"][0]
    assert result["document_filename"] == "contract.pdf"
    assert result["similarity"] == 0.87
    assert result["page_number"] == 5


def test_search_rejects_empty_query(client: TestClient) -> None:
    assert client.post("/api/v1/search", json={"query": ""}).status_code == 422


def test_search_rejects_oversized_top_k(client: TestClient) -> None:
    response = client.post("/api/v1/search", json={"query": "x", "top_k": 100})
    assert response.status_code == 422


def test_ask_returns_cited_answer_and_records_history(client: TestClient) -> None:
    response = client.post("/api/v1/qa/ask", json={"question": "What are the payment terms?"})

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Payment is due within 30 calendar days."
    assert body["confidence"] == 0.9
    assert body["model_used"]  # populated from settings
    assert body["latency_ms"] >= 0
    assert len(body["sources"]) == 1
    assert body["sources"][0]["chunk_id"] == str(_CHUNK.chunk_id)
    assert body["sources"][0]["document_filename"] == "contract.pdf"

    # The interaction is visible in history.
    history = client.get("/api/v1/qa/history").json()
    assert history["total"] == 1
    assert history["items"][0]["question"] == "What are the payment terms?"
    assert history["items"][0]["source_count"] == 1


def test_ask_rejects_blank_question(client: TestClient) -> None:
    assert client.post("/api/v1/qa/ask", json={"question": ""}).status_code == 422


def test_history_paginates(client: TestClient) -> None:
    for index in range(3):
        client.post("/api/v1/qa/ask", json={"question": f"question {index}?"})

    page = client.get("/api/v1/qa/history", params={"page": 1, "limit": 2}).json()
    assert page["total"] == 3
    assert len(page["items"]) == 2
    assert page["has_next"] is True


def test_ask_returns_503_when_no_llm_configured() -> None:
    """Without OPENAI_API_KEY (and no override), Q&A reports clearly instead of crashing."""
    app = create_app()
    app.dependency_overrides[get_embedder] = _FakeEmbedder
    app.dependency_overrides[get_chunk_repository] = lambda: _FakeChunks([_CHUNK])
    with TestClient(app) as client:
        response = client.post("/api/v1/qa/ask", json={"question": "anything?"})
    app.dependency_overrides.clear()

    assert response.status_code == 503
    assert "OPENAI_API_KEY" in response.json()["detail"]
