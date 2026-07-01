"""Use case: upload a document.

Orchestrates one user action end to end: validate the file, store its bytes,
create a `Document` record in the `uploaded` state, and persist it. It depends
only on the domain *ports* (StoragePort, DocumentRepository), so it can be unit
tested with simple fakes and works against any concrete implementation.

It does NOT process the document — extraction, chunking, and embedding happen
asynchronously later (Celery pipeline). This use case just gets the file safely
into the system and hands back a record the client can poll.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.domain.entities.document import Document
from app.domain.exceptions import EmptyFileError, FileTooLargeError
from app.domain.interfaces.repositories import DocumentRepository
from app.domain.interfaces.storage import StoragePort
from app.domain.value_objects.document_status import DocumentStatus
from app.domain.value_objects.file_type import FileType


def _utcnow() -> datetime:
    return datetime.now(UTC)


class UploadDocumentUseCase:
    """Validate, store, and record an uploaded document."""

    def __init__(
        self,
        *,
        storage: StoragePort,
        repository: DocumentRepository,
        max_file_size_bytes: int,
        clock: Callable[[], datetime] = _utcnow,
    ) -> None:
        self._storage = storage
        self._repository = repository
        self._max_file_size_bytes = max_file_size_bytes
        self._clock = clock

    async def execute(
        self,
        *,
        user_id: UUID,
        original_filename: str,
        content: bytes,
        content_type: str,
    ) -> Document:
        """Run the upload workflow and return the persisted Document.

        Raises (all domain errors; the API layer maps them to HTTP codes):
            UnsupportedFileTypeError: the MIME type is not accepted.
            EmptyFileError: the file has no content.
            FileTooLargeError: the file exceeds the configured size limit.
        """
        # 1. Validate before touching storage. `from_mime_type` raises
        #    UnsupportedFileTypeError for anything we cannot process.
        file_type = FileType.from_mime_type(content_type)
        if not content:
            raise EmptyFileError("Uploaded file is empty.")
        if len(content) > self._max_file_size_bytes:
            raise FileTooLargeError(
                f"File is {len(content)} bytes; limit is {self._max_file_size_bytes} bytes."
            )

        # 2. Persist the raw bytes; the storage path is recorded on the document.
        storage_path = await self._storage.save(content, filename=original_filename)

        # 3. Create and persist the domain record in the `uploaded` state.
        now = self._clock()
        document = Document(
            id=uuid4(),
            user_id=user_id,
            original_filename=original_filename,
            file_type=file_type,
            file_size_bytes=len(content),
            storage_path=storage_path,
            status=DocumentStatus.UPLOADED,
            created_at=now,
            updated_at=now,
        )
        return await self._repository.add(document)
