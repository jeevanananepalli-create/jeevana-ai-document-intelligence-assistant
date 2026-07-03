"""Use case: answer a natural-language question about the user's documents.

This is the hand-built RAG (Retrieval-Augmented Generation) pipeline, each step
a separate, testable operation behind a port:

    1. Embed the question              (EmbeddingPort)
    2. Retrieve the top-k similar chunks (ChunkRepository.search_similar)
    3. Generate a grounded answer       (LLMPort.generate_answer)
    4. Resolve citations                (map the model's used indices -> chunks)
    5. Record the interaction           (QueryHistoryRepository, best-effort)

Two honesty rules are enforced here rather than left to the model:
- If retrieval finds nothing, we answer "no relevant information" ourselves and
  never call the LLM — no context means any generated answer would be invented.
- Citations only include passages the model says it used, and only indices that
  actually exist (a hallucinated index is silently dropped).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.domain.entities.query_record import QueryRecord
from app.domain.interfaces.embeddings import EmbeddingPort
from app.domain.interfaces.llm import LLMPort
from app.domain.interfaces.repositories import ChunkRepository, QueryHistoryRepository
from app.domain.value_objects.search import ChunkSearchResult, QaResult, QaSource

logger = logging.getLogger(__name__)

_PREVIEW_CHARS = 200

_NO_CONTEXT_ANSWER = (
    "I could not find any relevant information in your documents to answer this "
    "question. Try uploading related documents or rephrasing the question."
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


class DocumentQAUseCase:
    """Answer questions over the user's documents with source citations."""

    def __init__(
        self,
        *,
        embedder: EmbeddingPort,
        chunks: ChunkRepository,
        llm: LLMPort,
        history: QueryHistoryRepository,
        model_name: str,
        clock: Callable[[], datetime] = _utcnow,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._embedder = embedder
        self._chunks = chunks
        self._llm = llm
        self._history = history
        self._model_name = model_name
        self._clock = clock
        self._monotonic = monotonic

    async def execute(
        self,
        *,
        user_id: UUID,
        question: str,
        top_k: int = 5,
        document_ids: list[UUID] | None = None,
    ) -> QaResult:
        started = self._monotonic()

        # 1-2. Embed the question and retrieve the most relevant chunks.
        query_embedding = await self._embedder.embed_text(question)
        retrieved = await self._chunks.search_similar(
            user_id, query_embedding, top_k=top_k, document_ids=document_ids
        )

        # 3-4. Generate a grounded answer, or answer honestly without the LLM
        # when there is no context to ground it in.
        if not retrieved:
            result = QaResult(
                answer=_NO_CONTEXT_ANSWER,
                confidence=0.0,
                sources=(),
                model_used=self._model_name,
                latency_ms=self._elapsed_ms(started),
            )
        else:
            rag_answer = await self._llm.generate_answer(
                question, [chunk.content for chunk in retrieved]
            )
            result = QaResult(
                answer=rag_answer.answer,
                confidence=rag_answer.confidence,
                sources=_resolve_citations(retrieved, rag_answer.used_source_indices),
                model_used=self._model_name,
                latency_ms=self._elapsed_ms(started),
            )

        # 5. Record history. Best-effort: a history hiccup must not lose the answer.
        await self._record_history(user_id, question, result)
        return result

    def _elapsed_ms(self, started: float) -> int:
        return int((self._monotonic() - started) * 1000)

    async def _record_history(self, user_id: UUID, question: str, result: QaResult) -> None:
        try:
            await self._history.add(
                QueryRecord(
                    id=uuid4(),
                    user_id=user_id,
                    question=question,
                    answer=result.answer,
                    confidence=result.confidence,
                    source_count=len(result.sources),
                    model_used=result.model_used,
                    latency_ms=result.latency_ms,
                    created_at=self._clock(),
                )
            )
        except Exception:
            logger.warning("Failed to record query history for user %s", user_id, exc_info=True)


def _resolve_citations(
    retrieved: list[ChunkSearchResult], used_indices: tuple[int, ...]
) -> tuple[QaSource, ...]:
    """Map the model's 'I used passages [0, 2]' back to real chunk citations.

    Indices outside the retrieved range are hallucinations and are dropped;
    duplicates are collapsed while preserving order.
    """
    seen: set[int] = set()
    sources: list[QaSource] = []
    for index in used_indices:
        if index in seen or not (0 <= index < len(retrieved)):
            continue
        seen.add(index)
        chunk = retrieved[index]
        sources.append(
            QaSource(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                document_filename=chunk.document_filename,
                page_number=chunk.page_number,
                content_preview=chunk.content[:_PREVIEW_CHARS],
                similarity=chunk.similarity,
            )
        )
    return tuple(sources)
