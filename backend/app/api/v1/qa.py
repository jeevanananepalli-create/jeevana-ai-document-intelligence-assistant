"""Question-answering endpoints (v1): ask a question, view past questions.

`POST /qa/ask` runs the hand-built RAG pipeline and returns a cited answer.
Requires an LLM to be configured (the dependency returns 503 otherwise).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.api.deps import (
    get_current_user_id,
    get_document_qa_use_case,
    get_query_history_repository,
)
from app.application.use_cases.document_qa import DocumentQAUseCase
from app.domain.interfaces.repositories import QueryHistoryRepository

router = APIRouter(prefix="/qa", tags=["qa"])


class AskRequest(BaseModel):
    """A natural-language question about the user's documents."""

    question: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)
    document_ids: list[UUID] | None = Field(
        default=None, description="Optionally restrict retrieval to these documents."
    )


class SourceCitation(BaseModel):
    chunk_id: UUID
    document_id: UUID
    document_filename: str
    page_number: int | None
    content_preview: str
    similarity: float


class QAResponse(BaseModel):
    answer: str
    sources: list[SourceCitation]
    confidence: float
    model_used: str
    latency_ms: int


class HistoryItem(BaseModel):
    id: UUID
    question: str
    answer: str
    confidence: float
    source_count: int
    model_used: str
    latency_ms: int
    created_at: datetime


class PaginatedHistory(BaseModel):
    items: list[HistoryItem]
    total: int
    page: int
    limit: int
    has_next: bool


@router.post("/ask", response_model=QAResponse, summary="Ask a question about your documents")
async def ask_question(
    request: AskRequest,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    use_case: Annotated[DocumentQAUseCase, Depends(get_document_qa_use_case)],
) -> QAResponse:
    """Answer a question using retrieved document context, with citations."""
    result = await use_case.execute(
        user_id=user_id,
        question=request.question,
        top_k=request.top_k,
        document_ids=request.document_ids,
    )
    return QAResponse(
        answer=result.answer,
        sources=[
            SourceCitation(
                chunk_id=source.chunk_id,
                document_id=source.document_id,
                document_filename=source.document_filename,
                page_number=source.page_number,
                content_preview=source.content_preview,
                similarity=source.similarity,
            )
            for source in result.sources
        ],
        confidence=result.confidence,
        model_used=result.model_used,
        latency_ms=result.latency_ms,
    )


@router.get("/history", response_model=PaginatedHistory, summary="Past questions and answers")
async def get_history(
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    history: Annotated[QueryHistoryRepository, Depends(get_query_history_repository)],
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PaginatedHistory:
    offset = (page - 1) * limit
    records = await history.list_for_user(user_id, limit=limit, offset=offset)
    total = await history.count_for_user(user_id)
    return PaginatedHistory(
        items=[
            HistoryItem(
                id=record.id,
                question=record.question,
                answer=record.answer,
                confidence=record.confidence,
                source_count=record.source_count,
                model_used=record.model_used,
                latency_ms=record.latency_ms,
                created_at=record.created_at,
            )
            for record in records
        ],
        total=total,
        page=page,
        limit=limit,
        has_next=offset + len(records) < total,
    )
