from src.chunking.base import Chunker, require_positive
from src.chunking.models import Chunk
from src.chunking.spans import SEPARATORS, Span, hard_split, pack, split_by_pattern, split_sentences


class SentenceChunker(Chunker):
    """Whole sentences, packed together up to max_chars.

    A chunk never ends mid-sentence unless one sentence alone is longer than
    max_chars; that sentence is cut between words. overlap_sentences repeats
    the last sentences of each chunk at the start of the next.
    """

    name = "sentence"

    def __init__(self, max_chars: int = 500, overlap_sentences: int = 0) -> None:
        require_positive(max_chars=max_chars)
        if overlap_sentences < 0:
            raise ValueError("overlap_sentences cannot be negative")
        self.max_chars = max_chars
        self.overlap_sentences = overlap_sentences

    def _chunk(self, text: str, document_id: str, metadata: dict, prefix: str) -> list[Chunk]:
        sentences = []
        for start, end in split_sentences(text):
            sentences.extend(fit_span(text, start, end, self.max_chars))

        spans = self._pack(sentences)
        return self._chunks_from_spans(text, spans, document_id, metadata, prefix)

    def _pack(self, sentences: list[Span]) -> list[Span]:
        """Greedy packing where each chunk restarts overlap_sentences back.

        The overlap shrinks when repeating those sentences would leave no
        room for a new one, so every chunk adds at least one sentence.
        """
        spans = []
        first = 0

        while first < len(sentences):
            last = first
            while (
                last + 1 < len(sentences)
                and sentences[last + 1][1] - sentences[first][0] <= self.max_chars
            ):
                last += 1
            spans.append((sentences[first][0], sentences[last][1]))

            if last + 1 >= len(sentences):
                break

            first = max(last + 1 - self.overlap_sentences, first + 1)
            while first <= last and sentences[last + 1][1] - sentences[first][0] > self.max_chars:
                first += 1

        return spans


def fit_span(text: str, start: int, end: int, max_chars: int):
    """Split one span between words, then characters, until each piece fits."""
    if end - start <= max_chars:
        return [(start, end)]

    words = split_by_pattern(text, start, end, SEPARATORS["word"])
    pieces = []
    for word_start, word_end in words:
        if word_end - word_start > max_chars:
            pieces.extend(hard_split(text, word_start, word_end, max_chars))
        else:
            pieces.append((word_start, word_end))

    return pack(pieces, max_chars)
