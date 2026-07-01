"""The Document entity — the central business object of the system.

A Document is an *entity*: it has identity (`id`) that persists even as its
attributes change. It is modelled as a frozen dataclass, so "changing" it
produces a new instance rather than mutating in place. This immutability removes
a whole class of bugs where one part of the code changes an object another part
still holds a reference to.

This is the pure-domain representation. The database/ORM row that persists it is
a separate concern in the infrastructure layer; the two are deliberately not the
same class.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from uuid import UUID

from app.domain.exceptions import InvalidStatusTransitionError
from app.domain.value_objects.document_status import DocumentStatus
from app.domain.value_objects.file_type import FileType


@dataclass(frozen=True, slots=True)
class Document:
    """A user's uploaded document and its processing state."""

    id: UUID
    user_id: UUID
    original_filename: str
    file_type: FileType
    file_size_bytes: int
    storage_path: str
    status: DocumentStatus
    created_at: datetime
    updated_at: datetime
    # Populated as the pipeline progresses; None until then.
    extracted_text: str | None = None
    page_count: int | None = None
    processing_error: str | None = None

    def with_status(
        self,
        new_status: DocumentStatus,
        *,
        updated_at: datetime,
        processing_error: str | None = None,
    ) -> Document:
        """Return a new Document moved to `new_status`, validating the transition.

        Raises:
            InvalidStatusTransitionError: the move is not allowed by the
                lifecycle rules in `DocumentStatus`.
        """
        if not self.status.can_transition_to(new_status):
            raise InvalidStatusTransitionError(
                f"Cannot move document {self.id} from {self.status} to {new_status}"
            )
        return replace(
            self,
            status=new_status,
            updated_at=updated_at,
            processing_error=processing_error,
        )

    def mark_completed(
        self, *, updated_at: datetime, extracted_text: str, page_count: int | None
    ) -> Document:
        """Return a completed copy carrying the extraction results.

        Raises InvalidStatusTransitionError if the current status cannot become
        `completed` (only `processing` can).
        """
        if not self.status.can_transition_to(DocumentStatus.COMPLETED):
            raise InvalidStatusTransitionError(
                f"Cannot complete document {self.id} from status {self.status}"
            )
        return replace(
            self,
            status=DocumentStatus.COMPLETED,
            updated_at=updated_at,
            extracted_text=extracted_text,
            page_count=page_count,
            processing_error=None,
        )

    def mark_failed(self, *, updated_at: datetime, error: str) -> Document:
        """Return a failed copy recording why processing failed."""
        if not self.status.can_transition_to(DocumentStatus.FAILED):
            raise InvalidStatusTransitionError(
                f"Cannot fail document {self.id} from status {self.status}"
            )
        return replace(
            self,
            status=DocumentStatus.FAILED,
            updated_at=updated_at,
            processing_error=error,
        )
