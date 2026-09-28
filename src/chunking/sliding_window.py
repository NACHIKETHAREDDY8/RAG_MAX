import re

from src.chunking.base import Chunker, require_positive
from src.chunking.models import Chunk


class SlidingWindowChunker(Chunker):
    """Windows of window_size words, moving step words at a time.

    Unlike fixed-size chunking it never cuts a word, and every window is
    full: the last one is moved back to end at the last word instead of
    being a short leftover. step < window_size makes windows overlap by
    window_size - step words; step == window_size makes them adjacent.
    """

    name = "sliding_window"

    def __init__(self, window_size: int = 100, step: int = 75) -> None:
        require_positive(window_size=window_size, step=step)
        if step > window_size:
            raise ValueError("step cannot exceed window_size, or words would be skipped")
        self.window_size = window_size
        self.step = step

    def _chunk(self, text: str, document_id: str, metadata: dict, prefix: str) -> list[Chunk]:
        words = [match.span() for match in re.finditer(r"\S+", text)]
        last_start = max(len(words) - self.window_size, 0)
        starts = list(range(0, last_start + 1, self.step))

        if starts[-1] != last_start:
            starts.append(last_start)

        spans = [
            (words[first][0], words[min(first + self.window_size, len(words)) - 1][1])
            for first in starts
        ]
        return self._chunks_from_spans(text, spans, document_id, metadata, prefix)
