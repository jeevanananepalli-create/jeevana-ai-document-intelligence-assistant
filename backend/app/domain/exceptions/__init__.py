"""Domain exceptions — errors expressed in business terms, not HTTP terms.

The domain raises `DocumentNotFoundError`, not `HTTPException(404)`. The API
layer is responsible for translating these into HTTP responses, which keeps the
domain independent of the transport mechanism.

All domain errors inherit from a single `DomainError` base, so callers can catch
the whole family with one `except DomainError` when they want to, or a specific
subclass when they need to.
"""

from __future__ import annotations


class DomainError(Exception):
    """Base class for all domain-level errors."""


class DocumentNotFoundError(DomainError):
    """A requested document does not exist (or is not owned by the caller)."""


class UnsupportedFileTypeError(DomainError):
    """The uploaded file's type is not one the pipeline can process."""


class FileTooLargeError(DomainError):
    """The uploaded file exceeds the maximum allowed size."""


class EmptyFileError(DomainError):
    """The uploaded file has no content."""


class InvalidStatusTransitionError(DomainError):
    """An attempt was made to move a document between incompatible statuses."""


__all__ = [
    "DomainError",
    "DocumentNotFoundError",
    "UnsupportedFileTypeError",
    "FileTooLargeError",
    "EmptyFileError",
    "InvalidStatusTransitionError",
]
