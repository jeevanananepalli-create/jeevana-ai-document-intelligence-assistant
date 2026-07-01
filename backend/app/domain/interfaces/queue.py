"""Processing-queue port — the contract for scheduling async document work.

The upload endpoint depends on this to say "process this document later" without
knowing that Celery/Redis exist. The concrete implementation enqueues a Celery
task; tests use a fake that just records the call. This keeps the API layer
decoupled from the task runner.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID


class DocumentProcessingQueue(Protocol):
    """Schedules background processing of an uploaded document."""

    def enqueue(self, document_id: UUID, user_id: UUID) -> None:
        """Request that the document be processed asynchronously."""
        ...
