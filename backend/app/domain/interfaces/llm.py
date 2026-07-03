"""LLM port — the abstract contract for AI document analysis.

The pipeline depends on this protocol, not on the OpenAI SDK, so the model
provider is swappable (OpenAI today, a local model or another vendor tomorrow)
and the pipeline is testable with a fake.

Deliberately narrow (interface segregation): Phase 3 only needs "analyze this
text". The RAG answer-generation method arrives with Phase 4 as its own port
method, added when something actually consumes it.
"""

from __future__ import annotations

from typing import Protocol

from app.domain.value_objects.document_analysis import DocumentAnalysis


class LLMPort(Protocol):
    """Produces structured AI analysis from document text."""

    async def analyze_document(self, text: str) -> DocumentAnalysis:
        """Summarize, extract entities from, and classify the given text.

        Implementations must return a fully-populated DocumentAnalysis or raise;
        callers treat any exception as "analysis unavailable" (the document
        itself must not fail because analysis did).
        """
        ...
