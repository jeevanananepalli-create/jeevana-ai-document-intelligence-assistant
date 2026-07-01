"""Tests for the TextChunker domain service.

These pin down the chunking contract with small, deterministic examples so the
behaviour (sizing, overlap, recursion, edge cases) is unambiguous.
"""

from __future__ import annotations

import pytest

from app.domain.services.text_chunker import TextChunker

# --- validation ------------------------------------------------------------


@pytest.mark.parametrize(
    "kwargs",
    [
        {"chunk_size": 0},
        {"chunk_size": -1},
        {"chunk_overlap": -1},
        {"chunk_size": 10, "chunk_overlap": 10},  # overlap must be < size
        {"chunk_size": 10, "chunk_overlap": 20},
    ],
)
def test_invalid_configuration_raises(kwargs: dict[str, int]) -> None:
    with pytest.raises(ValueError):
        TextChunker(**kwargs)


# --- empty / trivial input -------------------------------------------------


@pytest.mark.parametrize("text", ["", "   ", "\n\n\t  "])
def test_empty_or_whitespace_returns_no_chunks(text: str) -> None:
    assert TextChunker().chunk(text) == []


def test_short_text_returns_single_chunk() -> None:
    chunks = TextChunker(chunk_size=100, chunk_overlap=10).chunk("hello world")
    assert chunks == ["hello world"]


# --- core sizing & overlap (deterministic) ---------------------------------


def test_splits_with_expected_overlap() -> None:
    # 5 two-char words. With size=10/overlap=4 the packing is fully determined.
    chunks = TextChunker(chunk_size=10, chunk_overlap=4).chunk("aa bb cc dd ee")
    assert chunks == ["aa bb cc", "cc dd ee"]
    # "cc" is the carried-over overlap shared by both chunks.


def test_every_chunk_respects_chunk_size() -> None:
    text = " ".join(f"word{i}" for i in range(50))
    chunker = TextChunker(chunk_size=30, chunk_overlap=8)
    chunks = chunker.chunk(text)
    assert len(chunks) > 1
    assert all(len(chunk) <= 30 for chunk in chunks)


def test_no_words_are_lost() -> None:
    text = " ".join(f"word{i}" for i in range(50))
    chunks = TextChunker(chunk_size=30, chunk_overlap=8).chunk(text)
    seen = {word for chunk in chunks for word in chunk.split()}
    assert seen == {f"word{i}" for i in range(50)}


# --- recursion across separators -------------------------------------------


def test_prefers_paragraph_boundaries() -> None:
    # Small size forces each paragraph into its own chunk, split on "\n\n".
    chunks = TextChunker(chunk_size=15, chunk_overlap=3).chunk("para one here\n\npara two here")
    assert chunks == ["para one here", "para two here"]


def test_falls_back_to_characters_for_a_long_unbroken_token() -> None:
    # No spaces, so the splitter recurses down to characters.
    chunks = TextChunker(chunk_size=5, chunk_overlap=1).chunk("abcdefghijklmnop")
    assert len(chunks) > 1
    assert all(len(chunk) <= 5 for chunk in chunks)
    assert "".join(c.replace(" ", "") for c in chunks).startswith("abcde")


def test_oversized_token_kept_whole_without_a_character_fallback() -> None:
    # With no "" separator there is no finer split, so an oversized token is
    # returned intact rather than crashing or looping.
    chunker = TextChunker(chunk_size=5, chunk_overlap=1, separators=(" ",))
    assert chunker.chunk("hi bigword") == ["hi", "bigword"]


def test_recurses_into_finer_separators_for_a_long_paragraph() -> None:
    # The first paragraph fits; the second is far too big for one chunk, so the
    # splitter must recurse from "\n\n" down to word boundaries to break it up.
    long_paragraph = " ".join(f"w{i}" for i in range(20))
    chunks = TextChunker(chunk_size=12, chunk_overlap=3).chunk(f"short\n\n{long_paragraph}")
    assert chunks[0] == "short"
    assert len(chunks) > 2
    assert all(len(chunk) <= 12 for chunk in chunks)


# --- pluggable length function ---------------------------------------------


def test_custom_length_function_measures_in_words() -> None:
    word_count = lambda text: len(text.split())  # noqa: E731 - concise on purpose
    chunker = TextChunker(chunk_size=3, chunk_overlap=1, length_function=word_count)
    assert chunker.chunk("a b c d e") == ["a b c", "c d e"]


# --- determinism -----------------------------------------------------------


def test_chunking_is_deterministic() -> None:
    text = " ".join(f"token{i}" for i in range(40))
    chunker = TextChunker(chunk_size=25, chunk_overlap=6)
    assert chunker.chunk(text) == chunker.chunk(text)
