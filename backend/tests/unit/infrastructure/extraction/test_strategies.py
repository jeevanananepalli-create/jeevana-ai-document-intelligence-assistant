"""Tests for the concrete extraction strategies.

DOCX is tested for real (python-docx needs no external binary). The PDF/OCR
strategies are tested with their libraries monkeypatched, so the wrapping logic
is verified here and the real binaries are exercised in the Docker/CI environment.
"""

from __future__ import annotations

from io import BytesIO

import pytest

from app.infrastructure.extraction.docx_text import DocxExtractionStrategy
from app.infrastructure.extraction.image_ocr import ImageOcrExtractionStrategy
from app.infrastructure.extraction.pdf_ocr import PdfOcrExtractionStrategy
from app.infrastructure.extraction.pdf_text import PdfTextExtractionStrategy

# --- DOCX: real round-trip -------------------------------------------------


def _make_docx_bytes(paragraphs: list[str]) -> bytes:
    from docx import Document as DocxDocument  # local import; only needed in this test

    document = DocxDocument()
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_docx_extracts_paragraph_text() -> None:
    content = _make_docx_bytes(["First paragraph.", "Second paragraph."])
    result = DocxExtractionStrategy().extract(content)
    assert "First paragraph." in result.text
    assert "Second paragraph." in result.text
    assert result.page_count is None  # DOCX has no fixed pagination


# --- PDF text layer: pdfminer mocked ---------------------------------------


def test_pdf_text_returns_embedded_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.infrastructure.extraction.pdf_text.extract_text",
        lambda _stream: "  Hello from a digital PDF  ",
    )
    result = PdfTextExtractionStrategy().extract(b"%PDF-fake")
    assert result.text == "Hello from a digital PDF"


# --- Image OCR: Tesseract + PIL mocked -------------------------------------


def test_image_ocr_returns_recognised_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.infrastructure.extraction.image_ocr.Image.open", lambda _stream: "IMAGE"
    )
    monkeypatch.setattr(
        "app.infrastructure.extraction.image_ocr.pytesseract.image_to_string",
        lambda _image: "text on the image\n",
    )
    result = ImageOcrExtractionStrategy().extract(b"\x89PNG-fake")
    assert result.text == "text on the image"
    assert result.page_count == 1


# --- Scanned PDF OCR: pdf2image + Tesseract mocked -------------------------


def test_pdf_ocr_joins_per_page_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.infrastructure.extraction.pdf_ocr.convert_from_bytes",
        lambda _content: ["page-image-1", "page-image-2"],
    )
    monkeypatch.setattr(
        "app.infrastructure.extraction.pdf_ocr.pytesseract.image_to_string",
        lambda image: f"text of {image}",
    )
    result = PdfOcrExtractionStrategy().extract(b"%PDF-scanned")
    assert result.text == "text of page-image-1\n\ntext of page-image-2"
    assert result.page_count == 2
