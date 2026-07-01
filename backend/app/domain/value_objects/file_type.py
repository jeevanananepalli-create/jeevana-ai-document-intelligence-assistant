"""The kinds of files the system accepts, as a domain value object.

Centralising the supported types (and the mapping from MIME type) in one place
means validation logic is not scattered across the API and worker layers — they
all ask `FileType` what is allowed.
"""

from __future__ import annotations

from enum import StrEnum

from app.domain.exceptions import UnsupportedFileTypeError


class FileType(StrEnum):
    """A document file type the pipeline knows how to process."""

    PDF = "pdf"
    PNG = "png"
    JPG = "jpg"
    DOCX = "docx"

    @classmethod
    def from_mime_type(cls, mime_type: str) -> FileType:
        """Map a browser/HTTP MIME type to a supported `FileType`.

        Raises:
            UnsupportedFileTypeError: the MIME type is not one we accept. The API
                layer translates this into a 415 response; the domain stays
                ignorant of HTTP.
        """
        try:
            return _MIME_TO_FILE_TYPE[mime_type.lower().strip()]
        except KeyError:
            raise UnsupportedFileTypeError(
                f"Unsupported MIME type: {mime_type!r}. "
                f"Allowed: {', '.join(sorted(_MIME_TO_FILE_TYPE))}"
            ) from None


# A document can arrive under more than one MIME type (e.g. jpg vs jpeg), so the
# mapping is many-to-one onto FileType.
_MIME_TO_FILE_TYPE: dict[str, FileType] = {
    "application/pdf": FileType.PDF,
    "image/png": FileType.PNG,
    "image/jpeg": FileType.JPG,
    "image/jpg": FileType.JPG,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": FileType.DOCX,
}
