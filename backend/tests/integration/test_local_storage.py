"""Integration tests for LocalFileStorage against a real temp directory."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.infrastructure.storage.local_storage import LocalFileStorage


async def test_save_then_load_round_trips(tmp_path: Path) -> None:
    storage = LocalFileStorage(tmp_path)
    key = await storage.save(b"hello bytes", filename="note.txt")
    assert await storage.load(key) == b"hello bytes"


async def test_save_generates_safe_key_not_user_filename(tmp_path: Path) -> None:
    storage = LocalFileStorage(tmp_path)
    # A path-traversal attempt in the filename must not escape the base dir.
    key = await storage.save(b"data", filename="../../../etc/passwd")
    assert "/" not in key and "\\" not in key
    assert (tmp_path / key).is_file()  # stored safely inside the base directory


async def test_save_preserves_a_safe_extension(tmp_path: Path) -> None:
    storage = LocalFileStorage(tmp_path)
    key = await storage.save(b"%PDF", filename="contract.pdf")
    assert key.endswith(".pdf")


async def test_delete_removes_file_and_is_idempotent(tmp_path: Path) -> None:
    storage = LocalFileStorage(tmp_path)
    key = await storage.save(b"x", filename="a.bin")

    await storage.delete(key)
    with pytest.raises(FileNotFoundError):
        await storage.load(key)
    # Deleting again does not raise.
    await storage.delete(key)
