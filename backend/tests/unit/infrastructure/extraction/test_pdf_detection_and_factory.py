"""Tests for PDF digital-vs-scanned detection and the strategy factory.

The composite is tested with fake sub-strategies, so no PDF/OCR binaries are
needed — only the detection logic is under test.
"""

from __future__ import annotations

from app.domain.value_objects.extraction_result import ExtractionResult
from app.domain.value_objects.file_type import FileType
from app.infrastructure.extraction.docx_text import DocxExtractionStrategy
from app.infrastructure.extraction.factory import create_extraction_strategy
from app.infrastructure.extraction.image_ocr import ImageOcrExtractionStrategy
from app.infrastructure.extraction.pdf import PdfExtractionStrategy


class _StubStrategy:
    """Records whether it was called and returns a preset result."""

    def __init__(self, text: str) -> None:
        self.result = ExtractionResult(text=text, page_count=1)
        self.called = False

    def extract(self, content: bytes) -> ExtractionResult:
        self.called = True
        return self.result


def test_digital_pdf_uses_text_layer_and_skips_ocr() -> None:
    text_strategy = _StubStrategy("This is a real embedded text layer, plenty long.")
    ocr_strategy = _StubStrategy("ocr output")
    composite = PdfExtractionStrategy(text_strategy, ocr_strategy, min_text_chars=32)

    result = composite.extract(b"%PDF")

    assert result.text.startswith("This is a real embedded")
    assert ocr_strategy.called is False  # OCR not needed


def test_scanned_pdf_falls_back_to_ocr() -> None:
    text_strategy = _StubStrategy("")  # no usable text layer
    ocr_strategy = _StubStrategy("text recovered by OCR")
    composite = PdfExtractionStrategy(text_strategy, ocr_strategy, min_text_chars=32)

    result = composite.extract(b"%PDF")

    assert result.text == "text recovered by OCR"
    assert ocr_strategy.called is True


def test_threshold_boundary_prefers_text_layer() -> None:
    exactly_threshold = "x" * 32
    text_strategy = _StubStrategy(exactly_threshold)
    ocr_strategy = _StubStrategy("ocr")
    composite = PdfExtractionStrategy(text_strategy, ocr_strategy, min_text_chars=32)

    assert composite.extract(b"%PDF").text == exactly_threshold
    assert ocr_strategy.called is False


def test_factory_maps_file_types_to_strategies() -> None:
    assert isinstance(create_extraction_strategy(FileType.PDF), PdfExtractionStrategy)
    assert isinstance(create_extraction_strategy(FileType.DOCX), DocxExtractionStrategy)
    assert isinstance(create_extraction_strategy(FileType.PNG), ImageOcrExtractionStrategy)
    assert isinstance(create_extraction_strategy(FileType.JPG), ImageOcrExtractionStrategy)
