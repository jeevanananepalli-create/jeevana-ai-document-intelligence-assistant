"""Composite PDF strategy: choose digital text extraction or OCR automatically.

This encapsulates the "is the PDF text-based or scanned?" detection. It first
tries the fast, accurate text-layer extraction. If that yields too little text
(the tell-tale sign of a scanned, image-only PDF), it falls back to OCR.

The detection is a simple, explainable heuristic — a character threshold — which
is exactly why it lives in its own composite that can be unit-tested with fake
strategies, no PDF binaries required.
"""

from __future__ import annotations

from app.domain.interfaces.extraction import ExtractionStrategy
from app.domain.value_objects.extraction_result import ExtractionResult

# Below this many characters, we assume the text layer is absent/insufficient
# and the PDF is effectively a scan that needs OCR.
_DEFAULT_MIN_TEXT_CHARS = 32


class PdfExtractionStrategy:
    """Extract PDF text, falling back from digital extraction to OCR when needed."""

    def __init__(
        self,
        text_strategy: ExtractionStrategy,
        ocr_strategy: ExtractionStrategy,
        *,
        min_text_chars: int = _DEFAULT_MIN_TEXT_CHARS,
    ) -> None:
        self._text_strategy = text_strategy
        self._ocr_strategy = ocr_strategy
        self._min_text_chars = min_text_chars

    def extract(self, content: bytes) -> ExtractionResult:
        result = self._text_strategy.extract(content)
        if len(result.text) >= self._min_text_chars:
            return result
        # Sparse/empty text layer -> treat as scanned and OCR it.
        return self._ocr_strategy.extract(content)
