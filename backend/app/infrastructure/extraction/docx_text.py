"""DOCX extraction using python-docx.

A .docx file is a zip of XML; python-docx reads its paragraphs directly, so no
OCR is ever needed. Page count is not available (a DOCX has no fixed pagination
until it is rendered), so it is reported as None.
"""

from __future__ import annotations

from io import BytesIO

from docx import Document as DocxDocument

from app.domain.value_objects.extraction_result import ExtractionResult


class DocxExtractionStrategy:
    """Extract text from a Word .docx document."""

    def extract(self, content: bytes) -> ExtractionResult:
        document = DocxDocument(BytesIO(content))
        text = "\n".join(paragraph.text for paragraph in document.paragraphs)
        return ExtractionResult(text=text.strip(), page_count=None)
