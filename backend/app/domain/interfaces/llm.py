"""LLM port — the abstract contract for AI document analysis and RAG answers.

The pipeline depends on this protocol, not on the OpenAI SDK, so the model
provider is swappable (OpenAI today, a local model or another vendor tomorrow)
and everything is testable with a fake.

Two operations, both with structured (schema-bound) output:
- `analyze_document` — Phase 3: summary, entities, classification.
- `generate_answer`  — Phase 4: answer a question strictly from provided context
  passages, reporting which passages were actually used (for citations).
"""

from __future__ import annotations

from typing import Protocol

from app.domain.value_objects.document_analysis import DocumentAnalysis
from app.domain.value_objects.search import RagAnswer


class LLMPort(Protocol):
    """Produces structured AI outputs (analysis, grounded answers)."""

    async def analyze_document(self, text: str) -> DocumentAnalysis:
        """Summarize, extract entities from, and classify the given text.

        Implementations must return a fully-populated DocumentAnalysis or raise;
        callers treat any exception as "analysis unavailable" (the document
        itself must not fail because analysis did).
        """
        ...

    async def generate_answer(self, question: str, contexts: list[str]) -> RagAnswer:
        """Answer `question` using ONLY the numbered `contexts` passages.

        Implementations must instruct the model to say when the context does not
        contain the answer (low confidence, honest answer text) rather than
        inventing facts, and to report the indices of the passages it used.
        """
        ...
