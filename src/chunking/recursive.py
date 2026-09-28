from src.chunking.base import Chunker, require_overlap, require_positive
from src.chunking.models import Chunk
from src.chunking.spans import DEFAULT_SEPARATORS, SEPARATORS, Span, hard_split, pack, split_by_pattern


class RecursiveChunker(Chunker):
    """Split at the coarsest separator that works, then pack pieces back up.

    Text longer than chunk_size is split at sections, and any piece still
    too long is split at paragraphs, then lines, sentences, words and
    finally characters. The pieces are then joined back together greedily up
    to chunk_size, so chunks end at the most meaningful boundary available.

    separators are names from spans.SEPARATORS or raw regular expressions.
    """

    name = "recursive"

    def __init__(
        self,
        chunk_size: int = 500,
        overlap: int = 0,
        separators: list[str] | None = None,
    ) -> None:
        require_positive(chunk_size=chunk_size)
        require_overlap(overlap, chunk_size)
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.separators = list(separators or DEFAULT_SEPARATORS)
        self._patterns = [SEPARATORS.get(name, name) for name in self.separators]

    def _chunk(self, text: str, document_id: str, metadata: dict, prefix: str) -> list[Chunk]:
        return self._chunks_from_spans(
            text, self.spans(text, 0, len(text)), document_id, metadata, prefix
        )

    def spans(self, text: str, start: int, end: int) -> list[Span]:
        """Return chunk spans within text[start:end]."""
        pieces = self._split(text, start, end, 0)
        return pack(pieces, self.chunk_size, self.overlap)

    def _split(self, text: str, start: int, end: int, level: int) -> list[Span]:
        if end - start <= self.chunk_size:
            return [(start, end)]

        for next_level in range(level, len(self._patterns)):
            pieces = split_by_pattern(text, start, end, self._patterns[next_level])
            if len(pieces) > 1:
                return [
                    split
                    for piece_start, piece_end in pieces
                    for split in self._split(text, piece_start, piece_end, next_level + 1)
                ]

        return hard_split(text, start, end, self.chunk_size)
