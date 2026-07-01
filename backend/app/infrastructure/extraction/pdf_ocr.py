"""Scanned-PDF extraction: render each page to an image, then OCR it.

Used as the fallback for PDFs with no usable text layer. `pdf2image` renders
pages (needs the poppler binary) and `pytesseract` OCRs each one (needs the
Tesseract binary). Both are present in the Docker image; the logic is unit-tested
with these libraries mocked.
"""

from __future__ import annotations

import pytesseract
from pdf2image import convert_from_bytes

from app.domain.value_objects.extraction_result import ExtractionResult


class PdfOcrExtractionStrategy:
    """Extract text from a scanned PDF by OCR'ing each rendered page."""

    def extract(self, content: bytes) -> ExtractionResult:
        page_images = convert_from_bytes(content)
        page_texts = [pytesseract.image_to_string(image).strip() for image in page_images]
        combined = "\n\n".join(text for text in page_texts if text)
        return ExtractionResult(text=combined.strip(), page_count=len(page_images))
