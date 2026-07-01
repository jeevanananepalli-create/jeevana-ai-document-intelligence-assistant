"""Factory: select the extraction strategy for a given file type.

This is the single place that maps `FileType` to a concrete strategy, so callers
(the future Celery pipeline) just ask for "the strategy for this file" and stay
ignorant of pdfminer/Tesseract/python-docx entirely.
"""

from __future__ import annotations

from typing import assert_never

from app.domain.interfaces.extraction import ExtractionStrategy
from app.domain.value_objects.file_type import FileType
from app.infrastructure.extraction.docx_text import DocxExtractionStrategy
from app.infrastructure.extraction.image_ocr import ImageOcrExtractionStrategy
from app.infrastructure.extraction.pdf import PdfExtractionStrategy
from app.infrastructure.extraction.pdf_ocr import PdfOcrExtractionStrategy
from app.infrastructure.extraction.pdf_text import PdfTextExtractionStrategy


def create_extraction_strategy(file_type: FileType) -> ExtractionStrategy:
    """Return the extraction strategy appropriate for `file_type`."""
    match file_type:
        case FileType.PDF:
            # PDFs get the composite that auto-detects digital vs scanned.
            return PdfExtractionStrategy(PdfTextExtractionStrategy(), PdfOcrExtractionStrategy())
        case FileType.DOCX:
            return DocxExtractionStrategy()
        case FileType.PNG | FileType.JPG:
            return ImageOcrExtractionStrategy()
        case _:  # pragma: no cover - exhaustive; guards against a new FileType
            assert_never(file_type)
