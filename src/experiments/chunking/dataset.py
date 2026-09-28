"""The questions an experiment asks, and where their answers are in the corpus."""

import json
from dataclasses import dataclass
from pathlib import Path

from src.ingestion.models import Document


@dataclass(frozen=True)
class EvidenceSpan:
    """A passage the answer needs, located in one ingested document."""

    document_id: str
    start: int
    end: int
    text: str

    @property
    def length(self) -> int:
        return self.end - self.start


@dataclass(frozen=True)
class Question:
    id: str
    question: str
    filename: str
    # Every passage a complete answer needs; together they are the gold context.
    evidence: tuple[EvidenceSpan, ...]


def load_questions(path: str | Path, documents: list[Document]) -> list[Question]:
    """Load questions and find each evidence passage in the ingested text.

    The file is {"questions": [{"id", "question", "document", "evidence":
    [passage, ...]}]}, where document is a filename in the corpus and every
    passage is copied exactly from that document's ingested text. A passage
    that is not found raises ValueError, so a typo can never quietly score
    as "not retrieved".
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    by_filename: dict[str, list[Document]] = {}
    for document in documents:
        by_filename.setdefault(document.filename, []).append(document)

    questions = []
    problems = []

    for item in data["questions"]:
        candidates = by_filename.get(item["document"])
        if not candidates:
            problems.append(f"{item['id']}: no document named {item['document']}")
            continue

        spans = []
        for passage in item["evidence"]:
            span = _locate(passage, candidates)
            if span is None:
                problems.append(f"{item['id']}: passage not found in {item['document']}: {passage!r}")
            else:
                spans.append(span)

        questions.append(Question(item["id"], item["question"], item["document"], tuple(spans)))

    if problems:
        raise ValueError("Invalid questions file:\n" + "\n".join(problems))

    ids = [question.id for question in questions]
    if len(ids) != len(set(ids)):
        raise ValueError("Question ids must be unique.")

    return questions


def _locate(passage: str, documents: list[Document]) -> EvidenceSpan | None:
    for document in documents:
        start = document.text.find(passage)
        if start != -1:
            return EvidenceSpan(document.document_id, start, start + len(passage), passage)
    return None
