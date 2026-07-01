"""The result of extracting text from a document file.

A small, immutable value object returned by every extraction strategy, so the
rest of the pipeline works with a single uniform shape regardless of whether the
text came from a digital PDF, OCR, or a Word document.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    """Text extracted from a document, plus best-effort metadata."""

    text: str
    page_count: int | None = None  # None when the format has no fixed pages (e.g. DOCX)
