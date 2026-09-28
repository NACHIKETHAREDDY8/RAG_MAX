import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

from src.chunking.base import Chunker, require_positive
from src.chunking.models import Chunk
from src.chunking.sentence import fit_span
from src.chunking.spans import Span, split_sentences
from src.chunking.structure import parse_blocks

if TYPE_CHECKING:
    from src.embeddings.service import EmbeddingService

THRESHOLD_TYPES = ("percentile", "std", "absolute")

# A sentence opening with one of these points back at the one before it
# ("This retry storm is why..."), so a cut before it would separate a
# consequence from its cause even when the wording changes sharply.
REFERENCE_WORDS = {
    "this", "these", "that", "those", "it", "its", "they", "their", "them",
    "such", "both", "however", "therefore", "thus", "also", "and", "but",
}


@dataclass
class SemanticAnalysis:
    """Why the semantic chunker cut where it did, for inspection and reports."""

    sentences: list[Span]
    # distances[i] is the cosine distance between sentence i and i + 1.
    distances: list[float]
    threshold: float
    # Indexes i where a chunk ends after sentence i.
    breakpoints: list[int]
    # Cuts made regardless of distance (before a heading), and cuts that
    # are never made (after a heading, before a back-reference).
    forced: set[int] = field(default_factory=set)
    blocked: set[int] = field(default_factory=set)


class SemanticChunker(Chunker):
    """Group consecutive sentences whose meaning stays close.

    Each sentence is embedded together with buffer_size neighbours on each
    side (single sentences are too short to embed reliably). Where the
    cosine distance between one sentence's embedding and the next is
    unusually large, the topic has changed and a chunk ends. "Unusually
    large" is breakpoint_threshold interpreted by threshold_type:

    - percentile: above that percentile of this document's distances
    - std: more than that many standard deviations above the mean
    - absolute: above that distance

    Groups longer than max_chars are split again at their largest internal
    distance; groups shorter than min_chars are merged into the neighbour
    they are most similar to.

    Distances alone ignore two things a reader relies on. With
    respect_headings, a chunk always ends before a heading, never right
    after one, and small groups are not merged across a heading. With
    keep_references, no cut is made before a sentence that opens by
    pointing back ("This...", "Those...", "It..."; see REFERENCE_WORDS).

    Costs one embedding per sentence at indexing time.
    """

    name = "semantic"

    def __init__(
        self,
        embedding_service: "EmbeddingService",
        buffer_size: int = 1,
        threshold_type: str = "percentile",
        breakpoint_threshold: float = 85.0,
        max_chars: int = 1000,
        min_chars: int = 100,
        batch_size: int = 256,
        respect_headings: bool = True,
        keep_references: bool = True,
    ) -> None:
        require_positive(max_chars=max_chars, batch_size=batch_size)
        if threshold_type not in THRESHOLD_TYPES:
            raise ValueError(f"threshold_type must be one of {', '.join(THRESHOLD_TYPES)}")
        if buffer_size < 0 or min_chars < 0:
            raise ValueError("buffer_size and min_chars cannot be negative")
        if min_chars > max_chars:
            raise ValueError("min_chars cannot exceed max_chars")
        self.embedding_service = embedding_service
        self.buffer_size = buffer_size
        self.threshold_type = threshold_type
        self.breakpoint_threshold = breakpoint_threshold
        self.max_chars = max_chars
        self.min_chars = min_chars
        self.batch_size = batch_size
        self.respect_headings = respect_headings
        self.keep_references = keep_references

    def analyze(self, text: str) -> SemanticAnalysis:
        """Return the sentences, the distances between them, and where to cut."""
        sentences = [
            piece
            for start, end in split_sentences(text)
            for piece in fit_span(text, start, end, self.max_chars)
        ]
        distances = self._distances(text, sentences)
        threshold = self._threshold(distances)
        forced, blocked = self._rules(text, sentences)
        breakpoints = sorted(
            {
                index
                for index, distance in enumerate(distances)
                if distance > threshold and index not in blocked
            }
            | forced
        )
        return SemanticAnalysis(sentences, distances, threshold, breakpoints, forced, blocked)

    def _rules(self, text: str, sentences: list[Span]) -> tuple[set[int], set[int]]:
        """Return the cuts forced and blocked by headings and back-references."""
        forced: set[int] = set()
        blocked: set[int] = set()
        is_heading = [False] * len(sentences)

        if self.respect_headings:
            starts = {block.start for block in parse_blocks(text) if block.kind == "heading"}
            is_heading = [start in starts for start, _ in sentences]

        for index in range(len(sentences) - 1):
            following = sentences[index + 1]
            first_word = re.match(r"[A-Za-z]+", text[following[0] : following[1]])

            if is_heading[index]:
                blocked.add(index)
            elif is_heading[index + 1]:
                forced.add(index)
            elif (
                self.keep_references
                and first_word
                and first_word.group().lower() in REFERENCE_WORDS
            ):
                blocked.add(index)

        return forced, blocked

    def _chunk(self, text: str, document_id: str, metadata: dict, prefix: str) -> list[Chunk]:
        analysis = self.analyze(text)
        sentences, distances = analysis.sentences, analysis.distances

        groups = []
        first = 0
        for breakpoint in analysis.breakpoints + [len(sentences) - 1]:
            groups.extend(self._fit(sentences, distances, analysis.blocked, first, breakpoint))
            first = breakpoint + 1

        groups = self._merge_small(sentences, distances, analysis.forced, groups)
        spans = [(sentences[first][0], sentences[last][1]) for first, last in groups]
        return self._chunks_from_spans(text, spans, document_id, metadata, prefix)

    def _distances(self, text: str, sentences: list[Span]) -> list[float]:
        if len(sentences) < 2:
            return []

        windows = []
        for index in range(len(sentences)):
            first = max(index - self.buffer_size, 0)
            last = min(index + self.buffer_size, len(sentences) - 1)
            windows.append(text[sentences[first][0] : sentences[last][1]])

        embeddings = []
        for batch_start in range(0, len(windows), self.batch_size):
            embeddings.extend(
                self.embedding_service.embed_texts(
                    windows[batch_start : batch_start + self.batch_size]
                )
            )

        vectors = np.asarray(embeddings, dtype=np.float64)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        vectors = vectors / np.where(norms == 0, 1, norms)
        similarities = np.sum(vectors[:-1] * vectors[1:], axis=1)
        return [float(1 - similarity) for similarity in similarities]

    def _threshold(self, distances: list[float]) -> float:
        if not distances:
            return float("inf")
        if self.threshold_type == "percentile":
            return float(np.percentile(distances, self.breakpoint_threshold))
        if self.threshold_type == "std":
            return float(np.mean(distances) + self.breakpoint_threshold * np.std(distances))
        return self.breakpoint_threshold

    def _length(self, sentences: list[Span], first: int, last: int) -> int:
        return sentences[last][1] - sentences[first][0]

    def _fit(self, sentences, distances, blocked, first: int, last: int) -> list[tuple[int, int]]:
        """Split sentences first..last at their largest distances until each part fits.

        Blocked cuts are avoided unless there is no other way to fit.
        """
        if first == last or self._length(sentences, first, last) <= self.max_chars:
            return [(first, last)]

        candidates = [index for index in range(first, last) if index not in blocked]
        cut = max(candidates or range(first, last), key=lambda index: distances[index])
        return (
            self._fit(sentences, distances, blocked, first, cut)
            + self._fit(sentences, distances, blocked, cut + 1, last)
        )

    def _merge_small(self, sentences, distances, forced, groups):
        groups = list(groups)
        index = 0

        while index < len(groups):
            first, last = groups[index]
            if self._length(sentences, first, last) >= self.min_chars:
                index += 1
                continue

            # A forced cut (before a heading) is never merged away.
            candidates = []
            if index > 0 and first - 1 not in forced:
                candidates.append((distances[first - 1], index - 1))
            if index + 1 < len(groups) and last not in forced:
                candidates.append((distances[last], index + 1))

            for _, neighbour in sorted(candidates):
                merged = (min(first, groups[neighbour][0]), max(last, groups[neighbour][1]))
                if self._length(sentences, *merged) <= self.max_chars:
                    low = min(index, neighbour)
                    groups[low : low + 2] = [merged]
                    index = low
                    break
            else:
                index += 1

        return groups
