"""FastAPI dependency providers.

This is the composition root for request-scoped wiring: it maps the abstract
domain ports to their concrete implementations. Route handlers depend on the
ports (via these providers), never on the concrete classes, which is what keeps
the implementations swappable.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.use_cases.delete_document import DeleteDocumentUseCase
from app.application.use_cases.document_qa import DocumentQAUseCase
from app.application.use_cases.semantic_search import SemanticSearchUseCase
from app.application.use_cases.upload_document import UploadDocumentUseCase
from app.core.config import get_settings
from app.domain.interfaces.embeddings import EmbeddingPort
from app.domain.interfaces.llm import LLMPort
from app.domain.interfaces.queue import DocumentProcessingQueue
from app.domain.interfaces.repositories import (
    ChunkRepository,
    DocumentRepository,
    QueryHistoryRepository,
)
from app.domain.interfaces.storage import StoragePort
from app.infrastructure.database.session import get_db
from app.infrastructure.external_services.embeddings import SentenceTransformerEmbedding
from app.infrastructure.external_services.llm import OpenAILLM
from app.infrastructure.external_services.ollama import OllamaLLM
from app.infrastructure.repositories.postgres import PostgresDocumentRepository
from app.infrastructure.repositories.postgres_chunk import PostgresChunkRepository
from app.infrastructure.repositories.postgres_query_history import (
    PostgresQueryHistoryRepository,
)
from app.infrastructure.storage.local_storage import LocalFileStorage
from app.workers.queue import CeleryProcessingQueue


def get_document_repository(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DocumentRepository:
    """The PostgreSQL-backed repository, scoped to the request's DB session."""
    return PostgresDocumentRepository(session)


def get_chunk_repository(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ChunkRepository:
    return PostgresChunkRepository(session)


def get_query_history_repository(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> QueryHistoryRepository:
    return PostgresQueryHistoryRepository(session)


@lru_cache
def _embedder_singleton() -> SentenceTransformerEmbedding:
    """One embedder per process: the model is loaded once, then reused.

    Requires the `[ml]` extra in the API image — the same model that embedded
    the document chunks must embed the queries, or similarities are meaningless.
    """
    settings = get_settings()
    return SentenceTransformerEmbedding(settings.embedding_model, settings.embedding_dimension)


def get_embedder() -> EmbeddingPort:
    return _embedder_singleton()


def get_llm() -> LLMPort:
    """Return the configured LLM, or 503 if OpenAI is not configured.

    Q&A cannot work without a model; a clear 503 beats a confusing crash.
    """
    settings = get_settings()
    if settings.llm_provider == "ollama":
        return OllamaLLM(base_url=settings.ollama_base_url, model=settings.llm_model)
    if not settings.openai_api_key:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Q&A is not available: set OPENAI_API_KEY or switch to LLM_PROVIDER=ollama.",
        )
    return OpenAILLM(api_key=settings.openai_api_key, model=settings.llm_model)


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


def get_semantic_search_use_case(
    embedder: Annotated[EmbeddingPort, Depends(get_embedder)],
    chunks: Annotated[ChunkRepository, Depends(get_chunk_repository)],
) -> SemanticSearchUseCase:
    return SemanticSearchUseCase(embedder=embedder, chunks=chunks)


def get_document_qa_use_case(
    embedder: Annotated[EmbeddingPort, Depends(get_embedder)],
    chunks: Annotated[ChunkRepository, Depends(get_chunk_repository)],
    llm: Annotated[LLMPort, Depends(get_llm)],
    history: Annotated[QueryHistoryRepository, Depends(get_query_history_repository)],
) -> DocumentQAUseCase:
    return DocumentQAUseCase(
        embedder=embedder,
        chunks=chunks,
        llm=llm,
        history=history,
        model_name=get_settings().llm_model,
    )
