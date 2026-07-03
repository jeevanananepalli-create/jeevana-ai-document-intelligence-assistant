"""Semantic search endpoint (v1).

POST because the request carries a structured body (query + filters), and
because search input can exceed comfortable URL length limits.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import get_current_user_id, get_semantic_search_use_case
from app.application.use_cases.semantic_search import SemanticSearchUseCase

router = APIRouter(prefix="/search", tags=["search"])


class SearchRequest(BaseModel):
    """A natural-language search across the user's documents."""

    query: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=20)
    document_ids: list[UUID] | None = Field(
        default=None, description="Optionally restrict the search to these documents."
    )


class SearchResultItem(BaseModel):
    chunk_id: UUID
    document_id: UUID
    document_filename: str
    content: str
    similarity: float
    chunk_index: int
    page_number: int | None


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResultItem]
    total_results: int


@router.post("", response_model=SearchResponse, summary="Semantic search across documents")
async def search(
    request: SearchRequest,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    use_case: Annotated[SemanticSearchUseCase, Depends(get_semantic_search_use_case)],
) -> SearchResponse:
    """Return the chunks whose meaning best matches the query, best first."""
    results = await use_case.execute(
        user_id=user_id,
        query=request.query,
        top_k=request.top_k,
        document_ids=request.document_ids,
    )
    return SearchResponse(
        query=request.query,
        results=[
            SearchResultItem(
                chunk_id=result.chunk_id,
                document_id=result.document_id,
                document_filename=result.document_filename,
                content=result.content,
                similarity=result.similarity,
                chunk_index=result.chunk_index,
                page_number=result.page_number,
            )
            for result in results
        ],
        total_results=len(results),
    )
