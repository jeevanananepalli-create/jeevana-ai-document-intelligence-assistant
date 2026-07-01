"""Tests for ProcessDocumentUseCase.

The whole pipeline is exercised with fakes: no Celery, Redis, database, OCR, or
embedding model. This is the payoff of the ports design.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.application.use_cases.process_document import ProcessDocumentUseCase
from app.domain.entities.document import Document
from app.domain.entities.document_chunk import DocumentChunk
from app.domain.exceptions import DocumentNotFoundError
from app.domain.services.text_chunker import TextChunker
from app.domain.value_objects.document_status import DocumentStatus
from app.domain.value_objects.extraction_result import ExtractionResult
from app.domain.value_objects.file_type import FileType
from app.infrastructure.repositories.in_memory import InMemoryDocumentRepository

_NOW = datetime(2026, 7, 1, tzinfo=UTC)
_DIM = 384


class _FakeStorage:
    def __init__(self, content: bytes) -> None:
        self._content = content

    async def load(self, storage_path: str) -> bytes:
        return self._content


class _RaisingStorage:
    async def load(self, storage_path: str) -> bytes:
        raise RuntimeError("storage exploded")


class _FakeEmbedder:
    def __init__(self) -> None:
        self.batches: list[list[str]] = []

    @property
    def dimension(self) -> int:
        return _DIM

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        self.batches.append(texts)
        return [[0.1] * _DIM for _ in texts]

    async def embed_text(self, text: str) -> list[float]:
        return [0.1] * _DIM


class _FakeChunkRepo:
    def __init__(self) -> None:
        self.deleted: list[UUID] = []
        self.added: tuple[list[DocumentChunk], list[list[float]]] | None = None

    async def add_chunks(self, chunks: list[DocumentChunk], embeddings: list[list[float]]) -> None:
        self.added = (chunks, embeddings)

    async def delete_for_document(self, document_id: UUID) -> None:
        self.deleted.append(document_id)


class _FakeStrategy:
    def __init__(self, result: ExtractionResult) -> None:
        self._result = result

    def extract(self, content: bytes) -> ExtractionResult:
        return self._result


def _make_document(*, status: DocumentStatus = DocumentStatus.UPLOADED) -> Document:
    return Document(
        id=uuid4(),
        user_id=uuid4(),
        original_filename="doc.pdf",
        file_type=FileType.PDF,
        file_size_bytes=100,
        storage_path="k",
        status=status,
        created_at=_NOW,
        updated_at=_NOW,
    )


def _build_use_case(
    *,
    documents: InMemoryDocumentRepository,
    chunks: _FakeChunkRepo,
    storage: object,
    embedder: _FakeEmbedder,
    result: ExtractionResult,
    chunker: TextChunker,
) -> ProcessDocumentUseCase:
    return ProcessDocumentUseCase(
        documents=documents,
        chunks=chunks,  # type: ignore[arg-type]
        storage=storage,  # type: ignore[arg-type]
        embedder=embedder,
        chunker=chunker,
        strategy_factory=lambda _file_type: _FakeStrategy(result),
        clock=lambda: _NOW,
    )


async def test_pipeline_completes_and_stores_chunks() -> None:
    documents = InMemoryDocumentRepository()
    chunks = _FakeChunkRepo()
    embedder = _FakeEmbedder()
    document = await documents.add(_make_document())

    use_case = _build_use_case(
        documents=documents,
        chunks=chunks,
        storage=_FakeStorage(b"raw pdf bytes"),
        embedder=embedder,
        result=ExtractionResult(text="alpha beta gamma delta epsilon zeta", page_count=2),
        chunker=TextChunker(chunk_size=12, chunk_overlap=3),
    )
    await use_case.execute(document.id, document.user_id)

    stored = await documents.get(document.id, document.user_id)
    assert stored is not None
    assert stored.status is DocumentStatus.COMPLETED
    assert stored.page_count == 2
    assert stored.extracted_text == "alpha beta gamma delta epsilon zeta"

    # Chunks were replaced (idempotency) then written with matching embeddings.
    assert chunks.deleted == [document.id]
    assert chunks.added is not None
    written_chunks, written_embeddings = chunks.added
    assert len(written_chunks) == len(written_embeddings) > 1
    assert all(len(vector) == _DIM for vector in written_embeddings)


async def test_pipeline_with_no_extractable_text_completes_without_chunks() -> None:
    documents = InMemoryDocumentRepository()
    chunks = _FakeChunkRepo()
    embedder = _FakeEmbedder()
    document = await documents.add(_make_document())

    use_case = _build_use_case(
        documents=documents,
        chunks=chunks,
        storage=_FakeStorage(b"scanned-but-empty"),
        embedder=embedder,
        result=ExtractionResult(text="   ", page_count=1),
        chunker=TextChunker(),
    )
    await use_case.execute(document.id, document.user_id)

    stored = await documents.get(document.id, document.user_id)
    assert stored is not None and stored.status is DocumentStatus.COMPLETED
    assert chunks.deleted == [document.id]  # still cleared for idempotency
    assert chunks.added is None  # nothing to add
    assert embedder.batches == []  # embedder not called with no chunks


async def test_reprocessing_a_processing_document_is_allowed() -> None:
    documents = InMemoryDocumentRepository()
    document = await documents.add(_make_document(status=DocumentStatus.PROCESSING))

    use_case = _build_use_case(
        documents=documents,
        chunks=_FakeChunkRepo(),
        storage=_FakeStorage(b"x"),
        embedder=_FakeEmbedder(),
        result=ExtractionResult(text="some text here", page_count=1),
        chunker=TextChunker(),
    )
    await use_case.execute(document.id, document.user_id)

    stored = await documents.get(document.id, document.user_id)
    assert stored is not None and stored.status is DocumentStatus.COMPLETED


async def test_missing_document_raises() -> None:
    use_case = _build_use_case(
        documents=InMemoryDocumentRepository(),
        chunks=_FakeChunkRepo(),
        storage=_FakeStorage(b"x"),
        embedder=_FakeEmbedder(),
        result=ExtractionResult(text="t", page_count=1),
        chunker=TextChunker(),
    )
    with pytest.raises(DocumentNotFoundError):
        await use_case.execute(uuid4(), uuid4())


async def test_pipeline_failure_propagates() -> None:
    documents = InMemoryDocumentRepository()
    document = await documents.add(_make_document())
    use_case = _build_use_case(
        documents=documents,
        chunks=_FakeChunkRepo(),
        storage=_RaisingStorage(),
        embedder=_FakeEmbedder(),
        result=ExtractionResult(text="t", page_count=1),
        chunker=TextChunker(),
    )
    with pytest.raises(RuntimeError, match="storage exploded"):
        await use_case.execute(document.id, document.user_id)
