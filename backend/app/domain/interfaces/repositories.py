"""Repository ports — abstract persistence contracts for domain entities.

These are `typing.Protocol` classes: they declare *what* persistence the domain
needs without committing to *how* (PostgreSQL, in-memory, etc.). The
infrastructure layer provides concrete implementations; the application layer
depends only on these protocols, which is what makes the storage backend
swappable and the use cases testable with simple fakes.

Methods are async because the application runs on an async stack.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.domain.entities.document import Document
from app.domain.entities.document_chunk import DocumentChunk
from app.domain.entities.query_record import QueryRecord
from app.domain.value_objects.search import ChunkSearchResult


class DocumentRepository(Protocol):
    """Persistence operations for `Document` entities.

    Read/delete operations take a `user_id` so ownership is enforced at the data
    layer (a user can only ever see or remove their own documents) — defence in
    depth alongside API-level authorization.
    """

    async def add(self, document: Document) -> Document:
        """Persist a new document and return the stored entity."""
        ...

    async def get(self, document_id: UUID, user_id: UUID) -> Document | None:
        """Return the user's document by id, or None if it does not exist."""
        ...

    async def list_for_user(
        self, user_id: UUID, *, limit: int = 20, offset: int = 0
    ) -> list[Document]:
        """Return a page of the user's documents, newest first.

        Contract note: this is a LIST PROJECTION — implementations may omit the
        heavy fields (`extracted_text`, `analysis`) to keep listing cheap.
        Callers needing the full document must use `get()`.
        """
        ...

    async def update(self, document: Document) -> Document:
        """Persist changes to an existing document and return it."""
        ...

    async def delete(self, document_id: UUID, user_id: UUID) -> bool:
        """Delete the user's document; return True if a row was removed."""
        ...

    async def count_for_user(self, user_id: UUID) -> int:
        """Return the total number of documents owned by the user (for paging)."""
        ...


class ChunkRepository(Protocol):
    """Persistence operations for a document's text chunks and their embeddings."""

    async def add_chunks(self, chunks: list[DocumentChunk], embeddings: list[list[float]]) -> None:
        """Persist chunks paired positionally with their embedding vectors.

        `chunks[i]` is stored with `embeddings[i]`; the two lists must be the
        same length.
        """
        ...

    async def delete_for_document(self, document_id: UUID) -> None:
        """Remove all chunks for a document.

        Called before re-inserting so that re-processing a document is
        idempotent (running the pipeline twice leaves exactly one set of chunks).
        """
        ...

    async def search_similar(
        self,
        user_id: UUID,
        query_embedding: list[float],
        *,
        top_k: int = 5,
        document_ids: list[UUID] | None = None,
    ) -> list[ChunkSearchResult]:
        """Return the user's chunks most similar to `query_embedding`.

        Results are ordered by cosine similarity (highest first) and always
        scoped to the user's own documents — ownership enforcement lives in the
        query itself, not in the caller. `document_ids` optionally narrows the
        search to specific documents.
        """
        ...


class QueryHistoryRepository(Protocol):
    """Persistence for past Q&A interactions."""

    async def add(self, record: QueryRecord) -> QueryRecord:
        """Store one Q&A interaction."""
        ...

    async def list_for_user(
        self, user_id: UUID, *, limit: int = 20, offset: int = 0
    ) -> list[QueryRecord]:
        """Return a page of the user's past questions, newest first."""
        ...

    async def count_for_user(self, user_id: UUID) -> int:
        """Total number of history records for the user (for paging)."""
        ...
