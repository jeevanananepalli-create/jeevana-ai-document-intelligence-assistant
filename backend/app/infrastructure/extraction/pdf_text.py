"""Digital-PDF extraction using pdfminer.six.

Works for PDFs that contain an embedded text layer (i.e. were generated
digitally, not scanned). For scanned/image-only PDFs this returns little or no
text, which is exactly the signal the composite PdfExtractionStrategy uses to
fall back to OCR.
"""

from __future__ import annotations

from io import BytesIO

from pdfminer.high_level import extract_text
from pdfminer.pdfpage import PDFPage

from app.domain.value_objects.extraction_result import ExtractionResult


class PdfTextExtractionStrategy:
    """Extract the embedded text layer from a digital PDF."""

    def extract(self, content: bytes) -> ExtractionResult:
        text = extract_text(BytesIO(content)) or ""
        return ExtractionResult(text=text.strip(), page_count=_count_pages(content))


def _count_pages(content: bytes) -> int | None:
    """Best-effort page count; returns None if the PDF can't be parsed for pages."""
    try:
        return sum(1 for _ in PDFPage.get_pages(BytesIO(content)))
    except Exception:
        return None
