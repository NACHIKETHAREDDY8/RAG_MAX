from typing import Any

from src.chunking.base import Chunker, require_overlap, require_positive
from src.chunking.models import Chunk
from src.chunking.spans import Span


class FixedSizeChunker(Chunker):
    """Cut every chunk_size characters, repeating overlap characters.

    Ignores words and sentences entirely: the cheapest and most predictable
    strategy, and the one every other strategy is compared against.
    """

    name = "fixed"

    def __init__(self, chunk_size: int = 500, overlap: int = 50) -> None:
        require_positive(chunk_size=chunk_size)
        require_overlap(overlap, chunk_size)
        self.chunk_size = chunk_size
        self.overlap = overlap

    def _chunk(self, text: str, document_id: str, metadata: dict, prefix: str) -> list[Chunk]:
        return self._chunks_from_spans(
            text, self.spans(len(text)), document_id, metadata, prefix
        )

    def spans(self, length: int) -> list[Span]:
        spans = []
        step = self.chunk_size - self.overlap

        for start in range(0, length, step):
            spans.append((start, min(start + self.chunk_size, length)))
            # Before Phase 11 one more chunk was made here, lying entirely
            # inside this one's overlap.
            if start + self.chunk_size >= length:
                break

        return spans


def fixed_size_chunk(
    text: str,
    document_id: str,
    metadata: dict[str, Any],
    chunk_size: int = 500,
    overlap: int = 50,
    chunk_id_prefix: str | None = None,
) -> list[Chunk]:
    """Function form of FixedSizeChunker, kept for code written before Phase 11."""
    return FixedSizeChunker(chunk_size, overlap).chunk(
        text, document_id, metadata, chunk_id_prefix
    )
