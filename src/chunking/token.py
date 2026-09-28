from src.chunking.base import Chunker, require_overlap, require_positive
from src.chunking.models import Chunk
from src.chunking.spans import trim
from src.tokenization.tokenizer import get_tokenizer


class TokenChunker(Chunker):
    """max_tokens tokens per chunk, repeating overlap_tokens, using tiktoken.

    Measures text the way the embedding model does, so no chunk can exceed
    the model's input limit. Chunks are cut on token boundaries and then
    widened to whole characters: a token holding half of a multi-byte
    character (some emoji, CJK) never produces a broken character, at the
    cost of an occasional chunk one token over the limit.
    """

    name = "token"

    def __init__(self, max_tokens: int = 128, overlap_tokens: int = 16) -> None:
        require_positive(max_tokens=max_tokens)
        require_overlap(overlap_tokens, max_tokens, "max_tokens")
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens

    def _chunk(self, text: str, document_id: str, metadata: dict, prefix: str) -> list[Chunk]:
        tokenizer = get_tokenizer()
        tokens = tokenizer.encode(text)
        # offsets[i] is where token i's text starts.
        _, offsets = tokenizer.decode_with_offsets(tokens)
        boundaries = offsets + [len(text)]

        spans = []
        step = self.max_tokens - self.overlap_tokens
        for first in range(0, len(tokens), step):
            last = min(first + self.max_tokens, len(tokens))
            spans.append((boundaries[first], boundaries[last]))
            if last == len(tokens):
                break

        # Leading and trailing whitespace carries nothing to embed, and a
        # window of only blank lines is dropped.
        spans = [span for start, end in spans if (span := trim(text, start, end))]
        return self._chunks_from_spans(text, spans, document_id, metadata, prefix)
