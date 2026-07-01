"""Embedding port — abstract contract for turning text into vectors.

An embedding is a list of numbers that captures the *meaning* of a piece of
text, so that similar texts produce similar vectors (see docs/glossary.md). The
domain depends on this protocol, not on any specific model. The first
implementation uses a local sentence-transformers model; an OpenAI-backed
implementation can be swapped in via configuration without touching anything
that depends on this port.
"""

from __future__ import annotations

from typing import Protocol


class EmbeddingPort(Protocol):
    """Operations for converting text into vector embeddings."""

    @property
    def dimension(self) -> int:
        """The fixed length of every vector this embedder produces.

        Must match the `VECTOR(n)` column width in the database, which is why it
        is part of the contract rather than an implementation detail.
        """
        ...

    async def embed_text(self, text: str) -> list[float]:
        """Embed a single piece of text into one vector."""
        ...

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed many texts at once.

        Batching is much faster than embedding one item at a time, so the
        pipeline uses this for a document's chunks.
        """
        ...
