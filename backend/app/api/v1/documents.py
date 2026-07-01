"""Document endpoints (v1): upload.

The handler's job is purely HTTP: read the request, call the use case, and
translate domain outcomes into HTTP responses. All business rules live in the
domain/application layers; domain errors are mapped to status codes here.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.api.deps import (
    get_current_user_id,
    get_processing_queue,
    get_upload_document_use_case,
)
from app.application.use_cases.upload_document import UploadDocumentUseCase
from app.domain.exceptions import (
    EmptyFileError,
    FileTooLargeError,
    UnsupportedFileTypeError,
)
from app.domain.interfaces.queue import DocumentProcessingQueue
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

    # Hand off the slow work (extract/chunk/embed) to the worker.
    queue.enqueue(document.id, user_id)

    return UploadResponse(
        id=document.id,
        original_filename=document.original_filename,
        file_type=document.file_type,
        file_size_bytes=document.file_size_bytes,
        status=document.status,
        created_at=document.created_at,
    )
