"""TextChunker — splits a document's text into overlapping chunks.

Why chunking exists (see docs/glossary.md and docs/interview-preparation.md):
each chunk is embedded into a vector and retrieved independently during search.
Chunks must be small enough to be specific, large enough to carry context, and
they overlap so a fact that straddles a boundary still appears whole in at least
one chunk.

The algorithm is a *recursive* splitter. It tries to split on the most natural
boundary first (paragraphs), and only falls back to finer boundaries (lines,
sentences, words, characters) when a piece is still too big. This keeps chunks
aligned to meaningful boundaries instead of cutting mid-sentence.

Sizing is measured by a pluggable `length_function`. The default counts
characters, which needs no dependencies. In production a token-counting function
(e.g. a tokenizer) can be supplied so `chunk_size` means tokens — without
changing any of the logic here.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

# Boundaries tried in order, coarsest first: paragraph, line, sentence, word,
# and finally "" which means "split into individual characters".
_DEFAULT_SEPARATORS: tuple[str, ...] = ("\n\n", "\n", ". ", " ", "")


def _char_count(text: str) -> int:
    """Default length function: number of characters."""
    return len(text)


@dataclass(frozen=True)
class TextChunker:
    """Splits text into overlapping chunks of at most `chunk_size` units."""

    chunk_size: int = 512
    chunk_overlap: int = 64
    separators: tuple[str, ...] = _DEFAULT_SEPARATORS
    length_function: Callable[[str], int] = _char_count

    def __post_init__(self) -> None:
        if self.chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if self.chunk_overlap < 0:
            raise ValueError("chunk_overlap must be non-negative")
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")

    def chunk(self, text: str) -> list[str]:
        """Split `text` into a list of overlapping chunks.

        Returns an empty list for empty or whitespace-only input.
        """
        if not text or not text.strip():
            return []
        return self._split(text, self.separators)

    def _split(self, text: str, separators: tuple[str, ...]) -> list[str]:
        """Recursively split `text`, using the coarsest separator that applies."""
        # Pick the first separator that occurs in the text; "" is the last-resort
        # "split into characters" option and always matches.
        separator = separators[-1]
        finer_separators: tuple[str, ...] = ()
        for index, candidate in enumerate(separators):
            if candidate == "":
                separator = ""
                break
            if candidate in text:
                separator = candidate
                finer_separators = separators[index + 1 :]
                break

        pieces = list(text) if separator == "" else text.split(separator)
        pieces = [piece for piece in pieces if piece != ""]

        result: list[str] = []
        mergeable: list[str] = []
        for piece in pieces:
            if self.length_function(piece) < self.chunk_size:
                # Small enough to be merged with neighbours.
                mergeable.append(piece)
                continue
            # This piece alone is too big. Flush the pending small pieces, then
            # split this one further with the next-finer separators.
            if mergeable:
                result.extend(self._merge(mergeable, separator))
                mergeable = []
            if finer_separators:
                result.extend(self._split(piece, finer_separators))
            else:
                result.append(piece)  # cannot split further; keep as-is

        if mergeable:
            result.extend(self._merge(mergeable, separator))
        return result

    def _merge(self, pieces: list[str], separator: str) -> list[str]:
        """Greedily pack `pieces` into chunks, carrying an overlap between them."""
        separator_len = self.length_function(separator)
        chunks: list[str] = []
        window: list[str] = []
        window_len = 0

        for piece in pieces:
            piece_len = self.length_function(piece)
            join_len = separator_len if window else 0
            # If adding this piece would overflow the current window, finalise the
            # window as a chunk and slide it forward, keeping `chunk_overlap`
            # worth of trailing pieces as the start of the next chunk.
            if window and window_len + join_len + piece_len > self.chunk_size:
                chunks.append(separator.join(window))
                while window and window_len > self.chunk_overlap:
                    removed_len = self.length_function(window.pop(0))
                    window_len -= removed_len
                    if window:
                        window_len -= separator_len

            window.append(piece)
            window_len += piece_len + (separator_len if len(window) > 1 else 0)

        if window:
            chunks.append(separator.join(window))
        return chunks
