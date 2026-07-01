"""Celery-backed implementation of the DocumentProcessingQueue port.

Translates "process this document" into a Celery task enqueue. UUIDs are passed
as strings because task arguments must be JSON-serialisable.
"""

from __future__ import annotations

from uuid import UUID

from app.workers.tasks import process_document


class CeleryProcessingQueue:
    """Enqueues document processing onto the Celery/Redis queue."""

    def enqueue(self, document_id: UUID, user_id: UUID) -> None:
        process_document.delay(str(document_id), str(user_id))
