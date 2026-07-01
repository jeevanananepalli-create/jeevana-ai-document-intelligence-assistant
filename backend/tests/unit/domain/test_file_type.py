"""Tests for the FileType value object and its MIME-type mapping."""

from __future__ import annotations

import pytest

from app.domain.exceptions import UnsupportedFileTypeError
from app.domain.value_objects.file_type import FileType

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@pytest.mark.parametrize(
    ("mime", "expected"),
    [
        ("application/pdf", FileType.PDF),
        ("image/png", FileType.PNG),
        ("image/jpeg", FileType.JPG),
        ("image/jpg", FileType.JPG),
        (DOCX_MIME, FileType.DOCX),
    ],
)
def test_from_mime_type_maps_supported_types(mime: str, expected: FileType) -> None:
    assert FileType.from_mime_type(mime) is expected


def test_from_mime_type_is_case_and_whitespace_insensitive() -> None:
    assert FileType.from_mime_type("  APPLICATION/PDF  ") is FileType.PDF


def test_from_mime_type_rejects_unsupported_type() -> None:
    with pytest.raises(UnsupportedFileTypeError):
        FileType.from_mime_type("application/zip")
