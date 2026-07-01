"""In-memory implementation of the DocumentRepository.

Backed by a plain dict, this is a real, fully-working implementation of the
repository port — useful for fast tests and for running the app locally without
a database. The PostgreSQL implementation (added with the first migration)
implements the same port, so swapping between them changes nothing in the
application or domain layers.

Note: state lives only in this process's memory, so it is not shared with
separate worker processes and does not survive a restart. That is exactly why
the durable PostgreSQL implementation replaces it for real use.
"""

from __future__ import annotations

from uuid import UUID

from app.domain.entities.document import Document


class InMemoryDocumentRepository:
    """A dict-backed DocumentRepository."""

    def __init__(self) -> None:
        self._documents: dict[UUID, Document] = {}

    async def add(self, document: Document) -> Document:
        self._documents[document.id] = document
        return document

    async def get(self, document_id: UUID, user_id: UUID) -> Document | None:
        document = self._documents.get(document_id)
        # Enforce ownership: a user only ever sees their own documents.
        if document is not None and document.user_id == user_id:
            return document
        return None

    async def list_for_user(
        self, user_id: UUID, *, limit: int = 20, offset: int = 0
    ) -> list[Document]:
        owned = [doc for doc in self._documents.values() if doc.user_id == user_id]
        # Newest first, with id as a tiebreaker to match the SQL ordering.
        owned.sort(key=lambda doc: (doc.created_at, doc.id), reverse=True)
        return owned[offset : offset + limit]

    async def update(self, document: Document) -> Document:
        self._documents[document.id] = document
        return document

    async def delete(self, document_id: UUID, user_id: UUID) -> bool:
        document = self._documents.get(document_id)
        if document is not None and document.user_id == user_id:
            del self._documents[document_id]
            return True
        return False

    async def count_for_user(self, user_id: UUID) -> int:
        return sum(1 for doc in self._documents.values() if doc.user_id == user_id)
