"""Local embedding model implementation of the EmbeddingPort.

Uses a sentence-transformers model (default `all-MiniLM-L6-v2`, 384 dims) to turn
text into vectors — locally, with no API cost, and swappable for an OpenAI-backed
adapter later behind the same port.

Two deliberate implementation choices:

1. `sentence-transformers` (and its torch dependency) is imported lazily inside
   `_load_model`, not at module import time. That keeps this module importable —
   and the rest of the app testable with a fake EmbeddingPort — in environments
   where the heavy ML stack is not installed. It is installed via the optional
   `ml` extra and runs in the worker container.
2. The model is loaded once and reused, and encoding runs in a worker thread so
   it does not block the event loop.
"""

from __future__ import annotations

from typing import Any

import anyio


class SentenceTransformerEmbedding:
    """Embed text using a local sentence-transformers model."""

    def __init__(self, model_name: str, dimension: int) -> None:
        self._model_name = model_name
        self._dimension = dimension
        self._model: Any | None = None

    @property
    def dimension(self) -> int:
        return self._dimension

    def _load_model(self) -> Any:
        if self._model is None:
            # Imported here so importing this module never requires torch.
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self._model_name)
        return self._model

    async def embed_text(self, text: str) -> list[float]:
        vectors = await self.embed_batch([text])
        return vectors[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self._load_model()
        embeddings = await anyio.to_thread.run_sync(
            lambda: model.encode(texts, convert_to_numpy=True)
        )
        return [vector.tolist() for vector in embeddings]
