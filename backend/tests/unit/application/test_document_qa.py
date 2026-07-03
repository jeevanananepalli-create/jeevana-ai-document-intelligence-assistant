"""Tests for DocumentQAUseCase — the hand-built RAG pipeline, with fakes."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.application.use_cases.document_qa import DocumentQAUseCase
from app.application.use_cases.semantic_search import SemanticSearchUseCase
from app.domain.entities.query_record import QueryRecord
from app.domain.value_objects.search import ChunkSearchResult, RagAnswer
from app.infrastructure.repositories.in_memory import InMemoryQueryHistoryRepository

_NOW = datetime(2026, 7, 2, tzinfo=UTC)
_DIM = 8  # tiny vectors are fine for fakes


def _result(content: str, similarity: float) -> ChunkSearchResult:
    return ChunkSearchResult(
        chunk_id=uuid4(),
        document_id=uuid4(),
        document_filename="contract.pdf",
        content=content,
        similarity=similarity,
        chunk_index=0,
        page_number=3,
    )


class _FakeEmbedder:
    def __init__(self) -> None:
        self.embedded: list[str] = []

    @property
    def dimension(self) -> int:
        return _DIM

    async def embed_text(self, text: str) -> list[float]:
        self.embedded.append(text)
        return [0.5] * _DIM

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [[0.5] * _DIM for _ in texts]


class _FakeChunks:
    def __init__(self, results: list[ChunkSearchResult]) -> None:
        self._results = results
        self.calls: list[dict] = []

    async def search_similar(
        self,
        user_id: UUID,
        query_embedding: list[float],
        *,
        top_k: int = 5,
        document_ids: list[UUID] | None = None,
    ) -> list[ChunkSearchResult]:
        self.calls.append({"user_id": user_id, "top_k": top_k, "document_ids": document_ids})
        return self._results


class _FakeLLM:
    def __init__(self, answer: RagAnswer) -> None:
        self._answer = answer
        self.questions: list[str] = []
        self.contexts: list[list[str]] = []

    async def generate_answer(self, question: str, contexts: list[str]) -> RagAnswer:
        self.questions.append(question)
        self.contexts.append(contexts)
        return self._answer


class _ExplodingHistory:
    async def add(self, record: QueryRecord) -> QueryRecord:
        raise RuntimeError("history db down")


def _build(
    *,
    results: list[ChunkSearchResult],
    answer: RagAnswer,
    history: object | None = None,
) -> tuple[DocumentQAUseCase, _FakeChunks, _FakeLLM, InMemoryQueryHistoryRepository]:
    chunks = _FakeChunks(results)
    llm = _FakeLLM(answer)
    history_repo = InMemoryQueryHistoryRepository()
    use_case = DocumentQAUseCase(
        embedder=_FakeEmbedder(),
        chunks=chunks,  # type: ignore[arg-type]
        llm=llm,
        history=history if history is not None else history_repo,  # type: ignore[arg-type]
        model_name="gpt-4o-mini",
        clock=lambda: _NOW,
    )
    return use_case, chunks, llm, history_repo


async def test_happy_path_answers_with_resolved_citations() -> None:
    retrieved = [_result("Payment due in 30 days.", 0.9), _result("Termination clause.", 0.7)]
    answer = RagAnswer(
        answer="Payment is due within 30 days.", confidence=0.88, used_source_indices=(0,)
    )
    use_case, chunks, llm, history = _build(results=retrieved, answer=answer)
    user_id = uuid4()

    result = await use_case.execute(user_id=user_id, question="What are the payment terms?")

    assert result.answer == "Payment is due within 30 days."
    assert result.confidence == 0.88
    assert result.model_used == "gpt-4o-mini"
    assert result.latency_ms >= 0
    # Only the used passage is cited, mapped back to the real chunk.
    assert len(result.sources) == 1
    assert result.sources[0].chunk_id == retrieved[0].chunk_id
    assert result.sources[0].page_number == 3
    assert result.sources[0].content_preview.startswith("Payment due")
    # The LLM saw the chunk contents as its context.
    assert llm.contexts == [["Payment due in 30 days.", "Termination clause."]]
    # The interaction was recorded.
    assert await history.count_for_user(user_id) == 1
    (record,) = await history.list_for_user(user_id)
    assert record.question == "What are the payment terms?"
    assert record.source_count == 1


async def test_no_retrieved_chunks_answers_honestly_without_llm() -> None:
    answer = RagAnswer(answer="should never be used", confidence=1.0)
    use_case, _, llm, history = _build(results=[], answer=answer)
    user_id = uuid4()

    result = await use_case.execute(user_id=user_id, question="Anything?")

    assert "could not find" in result.answer.lower()
    assert result.confidence == 0.0
    assert result.sources == ()
    assert llm.questions == []  # LLM never called without context
    assert await history.count_for_user(user_id) == 1  # still recorded


async def test_hallucinated_and_duplicate_indices_are_dropped() -> None:
    retrieved = [_result("A", 0.9), _result("B", 0.8)]
    answer = RagAnswer(answer="x", confidence=0.5, used_source_indices=(1, 1, 7, -1, 0))
    use_case, _, _, _ = _build(results=retrieved, answer=answer)

    result = await use_case.execute(user_id=uuid4(), question="q")

    # 1 kept, duplicate 1 dropped, 7 and -1 out of range, 0 kept — order preserved.
    assert [s.chunk_id for s in result.sources] == [
        retrieved[1].chunk_id,
        retrieved[0].chunk_id,
    ]


async def test_history_failure_does_not_lose_the_answer() -> None:
    retrieved = [_result("A", 0.9)]
    answer = RagAnswer(answer="the answer", confidence=0.9, used_source_indices=(0,))
    use_case, _, _, _ = _build(results=retrieved, answer=answer, history=_ExplodingHistory())

    result = await use_case.execute(user_id=uuid4(), question="q")

    assert result.answer == "the answer"  # answer survives the history failure


async def test_filters_are_passed_to_retrieval() -> None:
    retrieved = [_result("A", 0.9)]
    answer = RagAnswer(answer="x", confidence=0.5, used_source_indices=(0,))
    use_case, chunks, _, _ = _build(results=retrieved, answer=answer)
    doc_ids = [uuid4()]

    await use_case.execute(user_id=uuid4(), question="q", top_k=3, document_ids=doc_ids)

    assert chunks.calls[0]["top_k"] == 3
    assert chunks.calls[0]["document_ids"] == doc_ids


async def test_semantic_search_use_case_embeds_and_delegates() -> None:
    retrieved = [_result("A", 0.9)]
    chunks = _FakeChunks(retrieved)
    embedder = _FakeEmbedder()
    use_case = SemanticSearchUseCase(embedder=embedder, chunks=chunks)  # type: ignore[arg-type]

    results = await use_case.execute(user_id=uuid4(), query="find things", top_k=7)

    assert embedder.embedded == ["find things"]
    assert chunks.calls[0]["top_k"] == 7
    assert results == retrieved
