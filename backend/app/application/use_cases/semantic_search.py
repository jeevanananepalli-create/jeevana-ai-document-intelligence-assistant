"""Use case: semantic search across a user's documents.

Two steps, both behind ports:

1. Embed the query text with the SAME model used for document chunks — vectors
   are only comparable inside one embedding space.
2. Ask the chunk repository for the nearest chunks by cosine similarity,
   scoped to the requesting user.

No LLM is involved: search is retrieval only, which is why it works even when
AI analysis/Q&A is not configured.
"""

from __future__ import annotations

from uuid import UUID

from app.domain.interfaces.embeddings import EmbeddingPort
from app.domain.interfaces.repositories import ChunkRepository
from app.domain.value_objects.search import ChunkSearchResult


class SemanticSearchUseCase:
    """Find the chunks whose meaning best matches a natural-language query."""

    def __init__(self, *, embedder: EmbeddingPort, chunks: ChunkRepository) -> None:
        self._embedder = embedder
        self._chunks = chunks

    async def execute(
        self,
        *,
        user_id: UUID,
        query: str,
        top_k: int = 5,
        document_ids: list[UUID] | None = None,
    ) -> list[ChunkSearchResult]:
        query_embedding = await self._embedder.embed_text(query)
        return await self._chunks.search_similar(
            user_id,
            query_embedding,
            top_k=top_k,
            document_ids=document_ids,
        )
