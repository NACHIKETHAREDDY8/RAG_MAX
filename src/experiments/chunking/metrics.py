"""Retrieval quality measured against gold evidence passages.

Everything is computed from character offsets, not from text matching:
each retrieved chunk and each piece of delivered context is a span of a
document, and each question's evidence is a set of spans. So the metrics
work for any strategy, including ones that prepend headings to chunk text.

Two views are measured:

- retrieved: the chunks the vector search ranked (children, for
  parent-child). Precision, hit rate and MRR describe the ranking.
- delivered: what the LLM would read after context expansion (the parents,
  for parent-child). Recall and completeness describe whether the answer is
  in there, and context_chars what it costs.
"""

from dataclasses import dataclass
from statistics import mean

from src.experiments.chunking.dataset import EvidenceSpan, Question

# A chunk is relevant when it holds at least this share of an evidence
# passage, or when at least this share of the chunk is evidence (a small
# chunk inside a long passage).
RELEVANCE_OVERLAP = 0.5
# An evidence passage counts as found when this share of it was delivered.
FOUND_COVERAGE = 0.8


@dataclass(frozen=True)
class TextSpan:
    document_id: str
    start: int
    end: int

    @property
    def length(self) -> int:
        return self.end - self.start


def overlap(span: TextSpan, evidence: EvidenceSpan) -> int:
    if span.document_id != evidence.document_id:
        return 0
    return max(0, min(span.end, evidence.end) - max(span.start, evidence.start))


def is_relevant(span: TextSpan, evidence: tuple[EvidenceSpan, ...]) -> bool:
    return any(
        (shared := overlap(span, passage)) > 0
        and (
            shared >= RELEVANCE_OVERLAP * passage.length
            or shared >= RELEVANCE_OVERLAP * span.length
        )
        for passage in evidence
    )


def covered_chars(passage: EvidenceSpan, spans: list[TextSpan]) -> int:
    """Characters of passage inside the union of spans (overlaps counted once)."""
    intervals = sorted(
        (max(span.start, passage.start), min(span.end, passage.end))
        for span in spans
        if overlap(span, passage)
    )
    covered = 0
    reach = passage.start
    for start, end in intervals:
        start = max(start, reach)
        if end > start:
            covered += end - start
            reach = end
    return covered


def question_metrics(
    question: Question,
    retrieved: list[TextSpan],
    delivered: list[TextSpan],
) -> dict:
    relevant = [is_relevant(span, question.evidence) for span in retrieved]
    first_relevant = relevant.index(True) + 1 if any(relevant) else None
    coverage = [covered_chars(passage, delivered) for passage in question.evidence]
    evidence_chars = sum(passage.length for passage in question.evidence)
    found = [
        covered >= FOUND_COVERAGE * passage.length
        for covered, passage in zip(coverage, question.evidence)
    ]

    return {
        "precision": sum(relevant) / len(retrieved) if retrieved else 0.0,
        "hit": float(any(relevant)),
        "reciprocal_rank": 1 / first_relevant if first_relevant else 0.0,
        "evidence_recall": sum(found) / len(found),
        "completeness": sum(coverage) / evidence_chars,
        "complete_answer": float(all(found)),
        "context_chars": sum(span.length for span in _distinct(delivered)),
    }


def average(rows: list[dict]) -> dict:
    if not rows:
        return {}
    return {key: mean(row[key] for row in rows) for key in rows[0]}


def _distinct(spans: list[TextSpan]) -> list[TextSpan]:
    return list(dict.fromkeys(spans))
