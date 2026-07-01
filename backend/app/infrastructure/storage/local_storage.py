"""Local filesystem implementation of the StoragePort.

Files are written under a configurable base directory. Two safety choices:

1. The stored filename is a freshly generated UUID, never the user's filename.
   This prevents path-traversal attacks (a malicious name like "../../etc/passwd"
   can never escape the storage directory) and avoids collisions.
2. Blocking file I/O is run in a worker thread via `anyio.to_thread`, so it does
   not stall the async event loop.
"""

from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

import anyio

# Only keep a short, alphanumeric extension from the original filename (for
# human-friendliness); everything else about the stored name is generated.
_SAFE_SUFFIX = re.compile(r"^\.[A-Za-z0-9]{1,8}$")


class LocalFileStorage:
    """Store and retrieve raw file bytes on the local filesystem."""

    def __init__(self, base_path: str | Path) -> None:
        self._base = Path(base_path)

    async def save(self, content: bytes, *, filename: str) -> str:
        """Write bytes under a generated key and return that key (the storage path)."""
        suffix = Path(filename).suffix
        safe_suffix = suffix if _SAFE_SUFFIX.match(suffix) else ""
        key = f"{uuid4().hex}{safe_suffix}"
        await anyio.to_thread.run_sync(self._write, key, content)
        return key

    async def load(self, storage_path: str) -> bytes:
        """Return the bytes stored at `storage_path`."""
        return await anyio.to_thread.run_sync(self._read, storage_path)

    async def delete(self, storage_path: str) -> None:
        """Remove the stored file; deleting a missing file is not an error."""
        await anyio.to_thread.run_sync(self._unlink, storage_path)

    # --- blocking helpers, run off the event loop --------------------------

    def _write(self, key: str, content: bytes) -> None:
        target = self._base / key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)

    def _read(self, storage_path: str) -> bytes:
        return (self._base / storage_path).read_bytes()

    def _unlink(self, storage_path: str) -> None:
        (self._base / storage_path).unlink(missing_ok=True)
