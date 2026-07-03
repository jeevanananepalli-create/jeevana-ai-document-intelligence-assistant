"""Value objects for semantic search and RAG question answering.

These are the shapes that flow through the retrieval side of the system:

- `ChunkSearchResult`: one chunk that matched a query, with its similarity score
  and enough document context (filename, page) to display or cite it.
- `RagAnswer`: what the LLM returns for a question — the answer text, which of
  the provided context passages it actually used, and its confidence. Keeping
  `used_source_indices` lets the pipeline cite only the chunks that contributed,
  not everything that was retrieved.
- `QaSource` / `QaResult`: the final, citation-resolved answer the API returns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ChunkSearchResult:
    """A document chunk matched by vector similarity search."""

    chunk_id: UUID
    document_id: UUID
    document_filename: str
    content: str
    similarity: float  # cosine similarity, 1.0 = identical meaning
    chunk_index: int
    page_number: int | None = None


@dataclass(frozen=True, slots=True)
class RagAnswer:
    """The LLM's structured response to a question over provided context."""

    answer: str
    confidence: float  # 0.0-1.0; low when the context doesn't contain the answer
    used_source_indices: tuple[int, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class QaSource:
    """A citation: the chunk an answer claim came from."""

    chunk_id: UUID
    document_id: UUID
    document_filename: str
    page_number: int | None
    content_preview: str
    similarity: float


@dataclass(frozen=True, slots=True)
class QaResult:
    """A complete question-answering result with resolved citations."""

    answer: str
    confidence: float
    sources: tuple[QaSource, ...]
    model_used: str
    latency_ms: int
