"""Extraction port — the abstract contract for turning a file into text.

The pipeline depends on this protocol, not on pdfminer/Tesseract/python-docx
directly, so extraction methods are swappable and the selection logic is
testable with fakes.

`extract` is synchronous: extraction is CPU-bound work (parsing, OCR) that runs
inside the Celery worker, not on the async web event loop.
"""

from __future__ import annotations

from typing import Protocol

from app.domain.value_objects.extraction_result import ExtractionResult


class ExtractionStrategy(Protocol):
    """Extracts text from the raw bytes of a single supported file type."""

    def extract(self, content: bytes) -> ExtractionResult:
        """Return the text (and best-effort page count) for `content`."""
        ...
