"""Shared fixtures for document API end-to-end tests.

The app is built with storage, repository, and the processing queue overridden by
test doubles (a temp directory, a fresh in-memory repository, and a fake queue),
so these tests need no real database, disk state, or Redis/Celery.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_document_repository, get_processing_queue, get_storage
from app.infrastructure.repositories.in_memory import InMemoryDocumentRepository
from app.infrastructure.storage.local_storage import LocalFileStorage
from app.main import create_app


class FakeQueue:
    """Records enqueue calls instead of talking to Celery/Redis."""

    def __init__(self) -> None:
        self.calls: list[tuple[UUID, UUID]] = []

    def enqueue(self, document_id: UUID, user_id: UUID) -> None:
        self.calls.append((document_id, user_id))


@dataclasses.dataclass
class Ctx:
    client: TestClient
    queue: FakeQueue
    repository: InMemoryDocumentRepository


@pytest.fixture
def ctx(tmp_path: Path) -> Iterator[Ctx]:
    app = create_app()
    repository = InMemoryDocumentRepository()
    queue = FakeQueue()
    app.dependency_overrides[get_storage] = lambda: LocalFileStorage(tmp_path)
    app.dependency_overrides[get_document_repository] = lambda: repository
    app.dependency_overrides[get_processing_queue] = lambda: queue
    with TestClient(app) as client:
        yield Ctx(client=client, queue=queue, repository=repository)
    app.dependency_overrides.clear()
