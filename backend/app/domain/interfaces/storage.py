"""Storage port — abstract contract for storing raw uploaded files.

The domain knows it needs to "save bytes and get back a path to them", but not
whether those bytes live on local disk or in cloud object storage (S3). A local
implementation is built first; switching to S3 later means writing a new
implementation of this protocol and changing nothing in the domain or
application layers.
"""

from __future__ import annotations

from typing import Protocol


class StoragePort(Protocol):
    """Persistence operations for raw file content."""

    async def save(self, content: bytes, *, filename: str) -> str:
        """Store file bytes and return an opaque storage path/key to retrieve them.

        The returned path is what gets recorded on the Document; callers should
        treat it as opaque (its format is the implementation's business).
        """
        ...

    async def load(self, storage_path: str) -> bytes:
        """Return the bytes previously stored at `storage_path`."""
        ...

    async def delete(self, storage_path: str) -> None:
        """Remove the stored file. Idempotent: deleting a missing file is fine."""
        ...
