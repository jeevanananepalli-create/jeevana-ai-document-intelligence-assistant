"""Image OCR using Tesseract (via pytesseract).

For uploaded images (PNG/JPG), there is no text layer at all, so OCR is the only
option. Requires the Tesseract binary to be installed at runtime (present in the
Docker image); the strategy logic is unit-tested with pytesseract mocked.
"""

from __future__ import annotations

from io import BytesIO

import pytesseract
from PIL import Image

from app.domain.value_objects.extraction_result import ExtractionResult


class ImageOcrExtractionStrategy:
    """Extract text from an image using optical character recognition."""

    def extract(self, content: bytes) -> ExtractionResult:
        image = Image.open(BytesIO(content))
        text = pytesseract.image_to_string(image)
        return ExtractionResult(text=text.strip(), page_count=1)
