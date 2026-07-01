"""PostgreSQL implementation of the DocumentRepository.

Implements the same port as InMemoryDocumentRepository, so the application layer
is unchanged when this replaces the in-memory version. Its single job is to
translate between the domain `Document` entity and the `DocumentModel` ORM row,
and to run the queries — ownership is enforced in every read/delete by filtering
on `user_id`.

Transactions are committed at the request boundary (see get_db); these methods
only stage changes (add / flush / statement execution).
"""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID

from sqlalchemy import CursorResult, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.document import Document
from app.domain.value_objects.document_status import DocumentStatus
from app.domain.value_objects.file_type import FileType
from app.infrastructure.database.models import DocumentModel


def _to_domain(model: DocumentModel) -> Document:
    """Map an ORM row to a pure domain entity."""
    return Document(
        id=model.id,
        user_id=model.user_id,
        original_filename=model.original_filename,
        file_type=FileType(model.file_type),
        file_size_bytes=model.file_size_bytes,
        storage_path=model.storage_path,
        status=DocumentStatus(model.status),
        created_at=model.created_at,
        updated_at=model.updated_at,
        extracted_text=model.extracted_text,
        page_count=model.page_count,
        processing_error=model.processing_error,
    )


def _to_model(document: Document) -> DocumentModel:
    """Map a domain entity to a new ORM row."""
    return DocumentModel(
        id=document.id,
        user_id=document.user_id,
        original_filename=document.original_filename,
        file_type=document.file_type.value,
        file_size_bytes=document.file_size_bytes,
        storage_path=document.storage_path,
        status=document.status.value,
        extracted_text=document.extracted_text,
        page_count=document.page_count,
        processing_error=document.processing_error,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


class PostgresDocumentRepository:
    """A DocumentRepository backed by PostgreSQL via SQLAlchemy."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, document: Document) -> Document:
        self._session.add(_to_model(document))
        await self._session.flush()
        return document

    async def get(self, document_id: UUID, user_id: UUID) -> Document | None:
        stmt = select(DocumentModel).where(
            DocumentModel.id == document_id,
            DocumentModel.user_id == user_id,
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_domain(model) if model is not None else None

    async def list_for_user(
        self, user_id: UUID, *, limit: int = 20, offset: int = 0
    ) -> list[Document]:
        stmt = (
            select(DocumentModel)
            .where(DocumentModel.user_id == user_id)
            # id as a tiebreaker makes ordering deterministic when timestamps tie.
            .order_by(DocumentModel.created_at.desc(), DocumentModel.id.desc())
            .limit(limit)
            .offset(offset)
        )
        models = (await self._session.execute(stmt)).scalars().all()
        return [_to_domain(model) for model in models]

    async def update(self, document: Document) -> Document:
        stmt = select(DocumentModel).where(DocumentModel.id == document.id)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        if model is None:
            # Nothing to update; treat as a no-op returning the given entity.
            return document
        model.status = document.status.value
        model.extracted_text = document.extracted_text
        model.page_count = document.page_count
        model.processing_error = document.processing_error
        model.updated_at = document.updated_at
        await self._session.flush()
        return document

    async def delete(self, document_id: UUID, user_id: UUID) -> bool:
        stmt = delete(DocumentModel).where(
            DocumentModel.id == document_id,
            DocumentModel.user_id == user_id,
        )
        # A DELETE returns a CursorResult, which carries rowcount (the number of
        # rows removed); the base Result type mypy infers does not expose it.
        result = cast("CursorResult[Any]", await self._session.execute(stmt))
        return result.rowcount > 0

    async def count_for_user(self, user_id: UUID) -> int:
        stmt = (
            select(func.count()).select_from(DocumentModel).where(DocumentModel.user_id == user_id)
        )
        return (await self._session.execute(stmt)).scalar_one()
