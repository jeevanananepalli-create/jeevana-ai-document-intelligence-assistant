"""FastAPI dependency providers.

This is the composition root for request-scoped wiring: it maps the abstract
domain ports to their concrete implementations. Route handlers depend on the
ports (via these providers), never on the concrete classes, which is what keeps
the implementations swappable.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.use_cases.delete_document import DeleteDocumentUseCase
from app.application.use_cases.upload_document import UploadDocumentUseCase
from app.core.config import get_settings
from app.domain.interfaces.queue import DocumentProcessingQueue
from app.domain.interfaces.repositories import DocumentRepository
from app.domain.interfaces.storage import StoragePort
from app.infrastructure.database.session import get_db
from app.infrastructure.repositories.postgres import PostgresDocumentRepository
from app.infrastructure.storage.local_storage import LocalFileStorage
from app.workers.queue import CeleryProcessingQueue


def get_document_repository(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DocumentRepository:
    """The PostgreSQL-backed repository, scoped to the request's DB session."""
    return PostgresDocumentRepository(session)


def get_storage() -> StoragePort:
    return LocalFileStorage(get_settings().storage_path)


def get_processing_queue() -> DocumentProcessingQueue:
    """The Celery-backed queue that schedules document processing."""
    return CeleryProcessingQueue()


# --- TEMPORARY: authentication placeholder ---------------------------------
# Real auth (decoding the JWT created by app.core.security) is the deferred
# Phase 1.3 feature. Until it lands, every request is attributed to a single
# fixed development user so the document flow can be built and tested. This is
# the ONLY stub in the upload feature; replacing it does not touch any other
# code, because everything downstream already takes a user_id.
_DEV_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


async def get_current_user_id() -> UUID:
    return _DEV_USER_ID


def get_upload_document_use_case(
    storage: Annotated[StoragePort, Depends(get_storage)],
    repository: Annotated[DocumentRepository, Depends(get_document_repository)],
) -> UploadDocumentUseCase:
    return UploadDocumentUseCase(
        storage=storage,
        repository=repository,
        max_file_size_bytes=get_settings().max_file_size_bytes,
    )


def get_delete_document_use_case(
    storage: Annotated[StoragePort, Depends(get_storage)],
    repository: Annotated[DocumentRepository, Depends(get_document_repository)],
) -> DeleteDocumentUseCase:
    return DeleteDocumentUseCase(storage=storage, repository=repository)
