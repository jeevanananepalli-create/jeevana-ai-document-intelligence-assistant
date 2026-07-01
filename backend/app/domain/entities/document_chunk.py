"""The DocumentChunk entity — one retrievable segment of a document's text.

A document's extracted text is split into overlapping chunks (see TextChunker).
Each chunk is later embedded into a vector and stored for similarity search.
The chunk's vector embedding is intentionally NOT part of this domain entity:
it is a derived artifact produced by the EmbeddingPort and attached at the
persistence layer, so the domain stays free of large float arrays and of any
particular embedding model.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class DocumentChunk:
    """A single, ordered slice of a document's text."""

    id: UUID
    document_id: UUID
    chunk_index: int  # 0-based position within the document
    content: str
    token_count: int
    page_number: int | None = None  # source page, when the extractor knows it
