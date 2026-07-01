"""Tests for the DocumentChunk entity."""

from __future__ import annotations

import dataclasses
from uuid import uuid4

import pytest

from app.domain.entities.document_chunk import DocumentChunk


def test_document_chunk_construction() -> None:
    chunk = DocumentChunk(
        id=uuid4(),
        document_id=uuid4(),
        chunk_index=0,
        content="Payment is due within 30 days.",
        token_count=7,
        page_number=5,
    )
    assert chunk.chunk_index == 0
    assert chunk.token_count == 7
    assert chunk.page_number == 5


def test_page_number_defaults_to_none() -> None:
    chunk = DocumentChunk(
        id=uuid4(),
        document_id=uuid4(),
        chunk_index=1,
        content="...",
        token_count=1,
    )
    assert chunk.page_number is None


def test_document_chunk_is_immutable() -> None:
    chunk = DocumentChunk(
        id=uuid4(), document_id=uuid4(), chunk_index=0, content="x", token_count=1
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        chunk.content = "changed"  # type: ignore[misc]
