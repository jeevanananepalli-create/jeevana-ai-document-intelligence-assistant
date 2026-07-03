"""Tests for the AI-analysis step of ProcessDocumentUseCase.

The analyzer is a fake LLMPort — no OpenAI, no network. The key behaviour under
test is the failure policy: analysis is best-effort and must never fail the
document.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.application.use_cases.process_document import ProcessDocumentUseCase
from app.domain.entities.document import Document
from app.domain.entities.document_chunk import DocumentChunk
from app.domain.services.text_chunker import TextChunker
from app.domain.value_objects.document_analysis import DocumentAnalysis, ExtractedEntity
from app.domain.value_objects.document_status import DocumentStatus
from app.domain.value_objects.extraction_result import ExtractionResult
from app.domain.value_objects.file_type import FileType
from app.infrastructure.repositories.in_memory import InMemoryDocumentRepository

_NOW = datetime(2026, 7, 2, tzinfo=UTC)
_DIM = 384

_ANALYSIS = DocumentAnalysis(
    summary="A service agreement between two companies.",
    document_type="contract",
    language="en",
    confidence=0.91,
    entities=(ExtractedEntity(name="Acme Corp", type="organization"),),
)


class _FakeAnalyzer:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.received: list[str] = []

    async def analyze_document(self, text: str) -> DocumentAnalysis:
        self.received.append(text)
        if self.fail:
            raise RuntimeError("LLM is down")
        return _ANALYSIS


class _FakeStorage:
    async def load(self, storage_path: str) -> bytes:
        return b"file-bytes"


class _FakeEmbedder:
    @property
    def dimension(self) -> int:
        return _DIM

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * _DIM for _ in texts]

    async def embed_text(self, text: str) -> list[float]:
        return [0.0] * _DIM


class _FakeChunkRepo:
    async def add_chunks(self, chunks: list[DocumentChunk], embeddings: list[list[float]]) -> None:
        pass

    async def delete_for_document(self, document_id: UUID) -> None:
        pass


class _FakeStrategy:
    def __init__(self, text: str) -> None:
        self._text = text

    def extract(self, content: bytes) -> ExtractionResult:
        return ExtractionResult(text=self._text, page_count=1)


def _make_document() -> Document:
    return Document(
        id=uuid4(),
        user_id=uuid4(),
        original_filename="doc.pdf",
        file_type=FileType.PDF,
        file_size_bytes=1,
        storage_path="k",
        status=DocumentStatus.UPLOADED,
        created_at=_NOW,
        updated_at=_NOW,
    )


def _build(
    documents: InMemoryDocumentRepository,
    *,
    analyzer: _FakeAnalyzer | None,
    text: str = "Some contract text worth analyzing.",
    analysis_max_chars: int = 100_000,
) -> ProcessDocumentUseCase:
    return ProcessDocumentUseCase(
        documents=documents,
        chunks=_FakeChunkRepo(),  # type: ignore[arg-type]
        storage=_FakeStorage(),  # type: ignore[arg-type]
        embedder=_FakeEmbedder(),
        chunker=TextChunker(),
        analyzer=analyzer,
        analysis_max_chars=analysis_max_chars,
        strategy_factory=lambda _ft: _FakeStrategy(text),
        clock=lambda: _NOW,
    )


async def test_analysis_results_are_persisted_on_the_document() -> None:
    documents = InMemoryDocumentRepository()
    document = await documents.add(_make_document())
    analyzer = _FakeAnalyzer()

    await _build(documents, analyzer=analyzer).execute(document.id, document.user_id)

    stored = await documents.get(document.id, document.user_id)
    assert stored is not None
    assert stored.status is DocumentStatus.COMPLETED
    assert stored.analysis == _ANALYSIS


async def test_llm_failure_does_not_fail_the_document() -> None:
    documents = InMemoryDocumentRepository()
    document = await documents.add(_make_document())

    await _build(documents, analyzer=_FakeAnalyzer(fail=True)).execute(
        document.id, document.user_id
    )

    stored = await documents.get(document.id, document.user_id)
    assert stored is not None
    assert stored.status is DocumentStatus.COMPLETED  # still completed
    assert stored.analysis is None  # just without analysis
    assert stored.processing_error is None  # and not marked as an error


async def test_no_analyzer_configured_skips_analysis() -> None:
    documents = InMemoryDocumentRepository()
    document = await documents.add(_make_document())

    await _build(documents, analyzer=None).execute(document.id, document.user_id)

    stored = await documents.get(document.id, document.user_id)
    assert stored is not None
    assert stored.status is DocumentStatus.COMPLETED
    assert stored.analysis is None


async def test_empty_extracted_text_skips_the_llm_call() -> None:
    documents = InMemoryDocumentRepository()
    document = await documents.add(_make_document())
    analyzer = _FakeAnalyzer()

    await _build(documents, analyzer=analyzer, text="   ").execute(document.id, document.user_id)

    assert analyzer.received == []  # LLM never called for empty text


async def test_long_text_is_truncated_before_analysis() -> None:
    documents = InMemoryDocumentRepository()
    document = await documents.add(_make_document())
    analyzer = _FakeAnalyzer()
    long_text = "word " * 1_000  # 5,000 chars

    await _build(documents, analyzer=analyzer, text=long_text, analysis_max_chars=100).execute(
        document.id, document.user_id
    )

    assert len(analyzer.received) == 1
    assert len(analyzer.received[0]) == 100  # truncated to the configured limit
