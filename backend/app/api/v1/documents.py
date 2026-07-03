"""Document endpoints (v1): upload, list, detail, status, and delete.

The handler's job is purely HTTP: read the request, call a use case or repository,
and translate domain outcomes into HTTP responses. All business rules live in the
domain/application layers; domain errors are mapped to status codes here.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from pydantic import BaseModel

from app.api.deps import (
    get_current_user_id,
    get_delete_document_use_case,
    get_document_repository,
    get_processing_queue,
    get_upload_document_use_case,
)
from app.application.use_cases.delete_document import DeleteDocumentUseCase
from app.application.use_cases.upload_document import UploadDocumentUseCase
from app.domain.entities.document import Document
from app.domain.exceptions import (
    EmptyFileError,
    FileTooLargeError,
    UnsupportedFileTypeError,
)
from app.domain.interfaces.queue import DocumentProcessingQueue
from app.domain.interfaces.repositories import DocumentRepository
from app.domain.value_objects.document_analysis import DocumentAnalysis
from app.domain.value_objects.document_status import DocumentStatus
from app.domain.value_objects.file_type import FileType

router = APIRouter(prefix="/documents", tags=["documents"])


class UploadResponse(BaseModel):
    """The 202 payload returned after a successful upload."""

    id: UUID
    original_filename: str
    file_type: FileType
    file_size_bytes: int
    status: DocumentStatus
    created_at: datetime


@router.post(
    "/upload",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=UploadResponse,
    summary="Upload a document for processing",
)
async def upload_document(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    use_case: Annotated[UploadDocumentUseCase, Depends(get_upload_document_use_case)],
    queue: Annotated[DocumentProcessingQueue, Depends(get_processing_queue)],
) -> UploadResponse:
    """Accept a file, store it, create a document record, and queue processing.

    Returns 202 Accepted: the file is received but processing (extraction,
    chunking, embedding) happens asynchronously in the Celery worker. The client
    polls the status endpoint for progress.
    """
    content = await file.read()
    try:
        document = await use_case.execute(
            user_id=user_id,
            original_filename=file.filename or "upload",
            content=content,
            content_type=file.content_type or "",
        )
    except UnsupportedFileTypeError as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, str(exc)) from exc
    except FileTooLargeError as exc:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, str(exc)) from exc
    except EmptyFileError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    # Hand off the slow work (extract/chunk/embed) to the worker VIA a background
    # task, not directly. Ordering matters: the DB session commits when the
    # request's dependencies tear down, and FastAPI runs background tasks AFTER
    # that teardown — so the worker can never pick up the job before the document
    # row is committed. Enqueuing inline here would race the commit.
    background_tasks.add_task(queue.enqueue, document.id, user_id)

    return UploadResponse(
        id=document.id,
        original_filename=document.original_filename,
        file_type=document.file_type,
        file_size_bytes=document.file_size_bytes,
        status=document.status,
        created_at=document.created_at,
    )


# --- read models -----------------------------------------------------------


class DocumentListItem(BaseModel):
    """Summary of a document, as returned in the paginated list."""

    id: UUID
    original_filename: str
    file_type: FileType
    file_size_bytes: int
    status: DocumentStatus
    page_count: int | None
    created_at: datetime


class PaginatedDocuments(BaseModel):
    """A page of documents plus pagination metadata."""

    items: list[DocumentListItem]
    total: int
    page: int
    limit: int
    has_next: bool


class EntityResponse(BaseModel):
    """One entity the AI analysis extracted."""

    name: str
    type: str


class AnalysisResponse(BaseModel):
    """The AI-derived analysis of a document."""

    summary: str
    document_type: str
    language: str
    confidence: float
    entities: list[EntityResponse]


class DocumentDetail(BaseModel):
    """Full document detail, including extracted text and analysis once processed."""

    id: UUID
    original_filename: str
    file_type: FileType
    file_size_bytes: int
    status: DocumentStatus
    page_count: int | None
    extracted_text: str | None
    processing_error: str | None
    analysis: AnalysisResponse | None
    created_at: datetime
    updated_at: datetime


class DocumentStatusResponse(BaseModel):
    """Lightweight processing-status payload for polling."""

    id: UUID
    status: DocumentStatus
    processing_error: str | None


class DeleteResponse(BaseModel):
    message: str


def _to_list_item(document: Document) -> DocumentListItem:
    return DocumentListItem(
        id=document.id,
        original_filename=document.original_filename,
        file_type=document.file_type,
        file_size_bytes=document.file_size_bytes,
        status=document.status,
        page_count=document.page_count,
        created_at=document.created_at,
    )


def _to_analysis(analysis: DocumentAnalysis | None) -> AnalysisResponse | None:
    if analysis is None:
        return None
    return AnalysisResponse(
        summary=analysis.summary,
        document_type=analysis.document_type,
        language=analysis.language,
        confidence=analysis.confidence,
        entities=[EntityResponse(name=e.name, type=e.type) for e in analysis.entities],
    )


def _to_detail(document: Document) -> DocumentDetail:
    return DocumentDetail(
        id=document.id,
        original_filename=document.original_filename,
        file_type=document.file_type,
        file_size_bytes=document.file_size_bytes,
        status=document.status,
        page_count=document.page_count,
        extracted_text=document.extracted_text,
        processing_error=document.processing_error,
        analysis=_to_analysis(document.analysis),
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


@router.get("", response_model=PaginatedDocuments, summary="List the user's documents")
async def list_documents(
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repository: Annotated[DocumentRepository, Depends(get_document_repository)],
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PaginatedDocuments:
    """Return one page of the current user's documents, newest first."""
    offset = (page - 1) * limit
    documents = await repository.list_for_user(user_id, limit=limit, offset=offset)
    total = await repository.count_for_user(user_id)
    return PaginatedDocuments(
        items=[_to_list_item(doc) for doc in documents],
        total=total,
        page=page,
        limit=limit,
        has_next=offset + len(documents) < total,
    )


@router.get("/{document_id}", response_model=DocumentDetail, summary="Get a document")
async def get_document(
    document_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repository: Annotated[DocumentRepository, Depends(get_document_repository)],
) -> DocumentDetail:
    document = await repository.get(document_id, user_id)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return _to_detail(document)


@router.get(
    "/{document_id}/status",
    response_model=DocumentStatusResponse,
    summary="Check a document's processing status",
)
async def get_document_status(
    document_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repository: Annotated[DocumentRepository, Depends(get_document_repository)],
) -> DocumentStatusResponse:
    document = await repository.get(document_id, user_id)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return DocumentStatusResponse(
        id=document.id, status=document.status, processing_error=document.processing_error
    )


@router.get(
    "/{document_id}/analysis",
    response_model=AnalysisResponse,
    summary="Get a document's AI analysis",
)
async def get_document_analysis(
    document_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repository: Annotated[DocumentRepository, Depends(get_document_repository)],
) -> AnalysisResponse:
    """Return the AI analysis (summary, entities, classification) for a document.

    404 with distinct messages when the document does not exist versus when it
    exists but has not been analyzed (still processing, analysis disabled, or
    the LLM step failed).
    """
    document = await repository.get(document_id, user_id)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    analysis = _to_analysis(document.analysis)
    if analysis is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Analysis not available for this document yet"
        )
    return analysis


@router.delete("/{document_id}", response_model=DeleteResponse, summary="Delete a document")
async def delete_document(
    document_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    use_case: Annotated[DeleteDocumentUseCase, Depends(get_delete_document_use_case)],
) -> DeleteResponse:
    deleted = await use_case.execute(document_id, user_id)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return DeleteResponse(message="Document deleted successfully")
