"""Text-extraction strategies — concrete implementations of ExtractionStrategy.

Each strategy handles one extraction method (digital PDF, OCR'd PDF, image OCR,
DOCX). The `factory` maps a `FileType` to the right strategy, and the composite
`PdfExtractionStrategy` decides between digital text and OCR for PDFs.
"""
