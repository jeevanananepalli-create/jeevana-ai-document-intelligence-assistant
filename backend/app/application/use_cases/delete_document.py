"""Use case: delete a document.

Removes both the database record (its chunks cascade away via the foreign key)
and the stored file. Ownership is enforced by scoping every operation to the
requesting user.
"""

from __future__ import annotations

from uuid import UUID

from app.domain.interfaces.repositories import DocumentRepository
from app.domain.interfaces.storage import StoragePort


class DeleteDocumentUseCase:
    """Delete a user's document and its stored file."""

    def __init__(self, *, repository: DocumentRepository, storage: StoragePort) -> None:
        self._repository = repository
        self._storage = storage

    async def execute(self, document_id: UUID, user_id: UUID) -> bool:
        """Delete the document; return False if it does not exist for this user."""
        document = await self._repository.get(document_id, user_id)
        if document is None:
            return False

        # Delete the record first (the source of truth; chunks cascade), then the
        # file. Storage deletion is idempotent, so a missing file is not an error.
        await self._repository.delete(document_id, user_id)
        await self._storage.delete(document.storage_path)
        return True
