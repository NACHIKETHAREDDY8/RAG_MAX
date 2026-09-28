"""Run one corpus and one question set through several chunking strategies.

Every strategy gets the same ingested documents, the same questions, the
same embedding model and the same k values; only the chunker differs. Each
strategy is indexed into its own fresh vector store through the production
IndexingService and searched through the production RetrievalService, so
the experiment measures the pipeline that app.py runs.

Output, under <output_dir>/<name>/:

    config.json              the resolved experiment configuration
    summary.json             every strategy's chunk statistics and metrics
    report.md                the generated comparison report
    case_studies.json        chunk boundaries around selected answers
    <label>/config.json      the strategy's parameters
    <label>/chunks.jsonl     every chunk, with offsets and parents
    <label>/index.faiss(.json)  the strategy's vector index
    <label>/retrieval.json   ranked results and metrics for every question
    <label>/metrics.json     the strategy's averaged metrics
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any

from src.chunking.base import Chunker
from src.chunking.models import Chunk
from src.chunking.registry import get_chunker
from src.chunking.semantic import SemanticChunker
from src.embeddings.base import EmbeddingProvider
from src.embeddings.service import EmbeddingService
from src.experiments.chunking.dataset import Question, load_questions
from src.experiments.chunking.metrics import TextSpan, average, question_metrics
from src.indexing.service import IndexingService
from src.ingestion.models import Document
from src.ingestion.pipeline import IngestionPipeline, find_documents
from src.repositories.vector_store_repository import VectorStoreRepository
from src.retrieval.service import RetrievalService, expand_to_context
from src.tokenization.tokenizer import count_tokens
from src.vector_store.faiss_store import FAISSVectorStore
from src.vector_store.models import SearchResult


@dataclass
class StrategySpec:
    label: str
    strategy: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExperimentConfig:
    name: str
    corpus_dir: Path
    questions_path: Path
    output_dir: Path
    embedding_model: str
    strategies: list[StrategySpec]
    # The k that headline tables report; metrics are computed for every k in ks.
    top_k: int = 3
    ks: list[int] = field(default_factory=lambda: [1, 3, 5])
    expand_context: bool = True
    # [{"question": id, "strategies": [label, ...]}] to explain in detail.
    case_studies: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_file(cls, path: str | Path) -> "ExperimentConfig":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            name=data["name"],
            corpus_dir=Path(data["corpus_dir"]),
            questions_path=Path(data["questions"]),
            output_dir=Path(data["output_dir"]),
            embedding_model=data["embedding_model"],
            strategies=[
                StrategySpec(label, spec["strategy"], spec.get("params", {}))
                for label, spec in data["strategies"].items()
            ],
            top_k=data.get("top_k", 3),
            ks=data.get("ks", [1, 3, 5]),
            expand_context=data.get("expand_context", True),
            case_studies=data.get("case_studies", []),
        )

    def __post_init__(self) -> None:
        if self.top_k not in self.ks:
            self.ks = sorted({*self.ks, self.top_k})
        labels = [spec.label for spec in self.strategies]
        if len(labels) != len(set(labels)):
            raise ValueError("Strategy labels must be unique.")


class CountingEmbeddingProvider(EmbeddingProvider):
    """Count the texts sent for embedding, to compare what strategies cost."""

    def __init__(self, provider: EmbeddingProvider) -> None:
        self.provider = provider
        self.count = 0

    def embed(self, text: str) -> list[float]:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        self.count += len(texts)
        return self.provider.embed_batch(texts)


@dataclass
class StrategyRun:
    spec: StrategySpec
    chunker: Chunker
    chunks: list[Chunk]
    stats: dict[str, Any]
    questions: list[dict[str, Any]]
    metrics: dict[int, dict[str, float]]
    by_document: dict[str, dict[str, float]]


def ingest_corpus(corpus_dir: Path, pipeline: IngestionPipeline | None = None) -> list[Document]:
    pipeline = pipeline or IngestionPipeline()
    return [
        document
        for path in find_documents(corpus_dir)
        for document in pipeline.ingest(path).documents
    ]


def run_experiment(
    config: ExperimentConfig,
    provider: EmbeddingProvider,
    dimension: int,
    log=print,
) -> dict[str, Any]:
    """Run every strategy, write all outputs, and return the summary."""
    from src.experiments.chunking.report import render_report

    documents = ingest_corpus(config.corpus_dir)
    questions = load_questions(config.questions_path, documents)
    run_dir = config.output_dir / config.name
    run_dir.mkdir(parents=True, exist_ok=True)

    log(f"{len(documents)} documents, {len(questions)} questions, k={config.ks}")

    runs = []
    for spec in config.strategies:
        log(f"Running {spec.label} ({spec.strategy})")
        run = run_strategy(spec, documents, questions, provider, dimension, config, run_dir / spec.label)
        runs.append(run)
        headline = run.metrics[config.top_k]
        log(
            f"  {run.stats['chunks']} chunks, completeness@{config.top_k} "
            f"{headline['completeness']:.2f}, MRR {headline['reciprocal_rank']:.2f}"
        )

    summary = {
        "name": config.name,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "embedding_model": config.embedding_model,
        "top_k": config.top_k,
        "ks": config.ks,
        "expand_context": config.expand_context,
        "documents": [
            {
                "filename": document.filename,
                "document_id": document.document_id,
                "source_type": document.metadata.get("source_type"),
                "chars": len(document.text),
            }
            for document in documents
        ],
        "questions": [
            {"id": question.id, "question": question.question, "document": question.filename}
            for question in questions
        ],
        "strategies": {
            run.spec.label: {
                "strategy": run.spec.strategy,
                "params": run.chunker.config(),
                "stats": run.stats,
                "metrics": {str(k): values for k, values in run.metrics.items()},
                "by_document": run.by_document,
                "per_question": {
                    row["id"]: row["metrics"][str(config.top_k)] for row in run.questions
                },
            }
            for run in runs
        },
    }
    case_studies = build_case_studies(config, documents, questions, runs)

    _write_json(run_dir / "config.json", _config_record(config))
    _write_json(run_dir / "summary.json", summary)
    _write_json(run_dir / "case_studies.json", case_studies)
    (run_dir / "report.md").write_text(render_report(summary, case_studies), encoding="utf-8")
    log(f"Wrote {run_dir / 'report.md'}")

    return summary


def run_strategy(
    spec: StrategySpec,
    documents: list[Document],
    questions: list[Question],
    provider: EmbeddingProvider,
    dimension: int,
    config: ExperimentConfig,
    out_dir: Path,
) -> StrategyRun:
    out_dir.mkdir(parents=True, exist_ok=True)
    counter = CountingEmbeddingProvider(provider)
    embedding_service = EmbeddingService(counter, dimension=dimension)
    chunker = get_chunker(spec.strategy, embedding_service=embedding_service, **spec.params)
    repository = VectorStoreRepository(FAISSVectorStore(dimension), out_dir / "index.faiss")
    indexing = IndexingService(embedding_service, repository, chunker=chunker)

    chunks = [chunk for document in documents for chunk in indexing.chunk_and_index(document)]
    embedded_for_indexing = counter.count
    repository.save()

    by_id = {chunk.chunk_id: chunk for chunk in chunks}
    retrieval = RetrievalService(embedding_service, repository, top_k=max(config.ks))
    expand = config.expand_context and chunker.provides_context
    rows = []

    for question in questions:
        ranked = retrieval.retrieve(question.question)
        metrics = {}
        for k in config.ks:
            top = ranked[:k]
            delivered = expand_to_context(top) if expand else top
            metrics[str(k)] = question_metrics(
                question,
                [_span(by_id[result.chunk_id]) for result in top],
                [_delivered_span(result, by_id) for result in delivered],
            )
        rows.append(
            {
                "id": question.id,
                "question": question.question,
                "retrieved": [
                    {
                        "rank": rank,
                        "chunk_id": result.chunk_id,
                        "score": round(result.score, 6),
                        "filename": result.filename,
                        "start": by_id[result.chunk_id].start,
                        "end": by_id[result.chunk_id].end,
                        "context_id": by_id[result.chunk_id].context_id,
                    }
                    for rank, result in enumerate(ranked, start=1)
                ],
                "metrics": metrics,
            }
        )

    stats = chunk_stats(chunks, documents, embedded_for_indexing)
    averaged = {k: average([row["metrics"][str(k)] for row in rows]) for k in config.ks}
    by_document = {
        document.filename: average(
            [
                row["metrics"][str(config.top_k)]
                for row, question in zip(rows, questions)
                if question.filename == document.filename
            ]
        )
        for document in documents
    }

    _write_json(out_dir / "config.json", {"label": spec.label, "strategy": spec.strategy, "params": chunker.config(), "expand_context": expand})
    _write_jsonl(out_dir / "chunks.jsonl", [_chunk_record(chunk) for chunk in chunks])
    _write_json(out_dir / "retrieval.json", rows)
    _write_json(out_dir / "metrics.json", {"stats": stats, "metrics": {str(k): v for k, v in averaged.items()}, "by_document": by_document})

    return StrategyRun(spec, chunker, chunks, stats, rows, averaged, by_document)


def chunk_stats(chunks: list[Chunk], documents: list[Document], embedded_for_indexing: int) -> dict[str, Any]:
    retrievable = [chunk for chunk in chunks if chunk.retrievable]
    sizes = [len(chunk.text) for chunk in retrievable]
    names = {document.document_id: document.filename for document in documents}
    per_document: dict[str, int] = {}
    for chunk in retrievable:
        per_document[names[chunk.document_id]] = per_document.get(names[chunk.document_id], 0) + 1

    return {
        "chunks": len(retrievable),
        "context_chunks": len(chunks) - len(retrievable),
        "avg_chars": mean(sizes),
        "median_chars": median(sizes),
        "min_chars": min(sizes),
        "max_chars": max(sizes),
        "avg_tokens": mean(count_tokens(chunk.text) for chunk in retrievable),
        "embedded_texts": embedded_for_indexing,
        "chunks_by_document": per_document,
    }


def build_case_studies(
    config: ExperimentConfig,
    documents: list[Document],
    questions: list[Question],
    runs: list[StrategyRun],
) -> list[dict[str, Any]]:
    """Describe how each strategy's chunk boundaries fall around an answer."""
    by_question = {question.id: question for question in questions}
    by_label = {run.spec.label: run for run in runs}
    texts = {document.document_id: document.text for document in documents}
    studies = []

    for case in config.case_studies:
        question = by_question[case["question"]]
        study = {"question": question.id, "text": question.question, "evidence": [], "strategies": {}}
        study["evidence"] = [asdict(passage) for passage in question.evidence]

        for label in case["strategies"]:
            if label not in by_label:
                continue
            run = by_label[label]
            row = next(row for row in run.questions if row["id"] == question.id)
            ranks = {item["chunk_id"]: item["rank"] for item in row["retrieved"]}
            entry = {
                "metrics": row["metrics"][str(config.top_k)],
                "top_results": row["retrieved"][: config.top_k],
                "passages": [],
            }

            for passage in question.evidence:
                holders = sorted(
                    (
                        chunk
                        for chunk in run.chunks
                        if chunk.retrievable
                        and chunk.document_id == passage.document_id
                        and chunk.start < passage.end
                        and passage.start < chunk.end
                    ),
                    key=lambda chunk: chunk.start,
                )
                text = texts[passage.document_id]
                entry["passages"].append(
                    {
                        "passage": passage.text,
                        "whole_in_one_chunk": any(
                            chunk.start <= passage.start and passage.end <= chunk.end
                            for chunk in holders
                        ),
                        "chunks": [
                            {
                                "chunk_id": chunk.chunk_id,
                                "start": chunk.start,
                                "end": chunk.end,
                                "rank": ranks.get(chunk.chunk_id),
                                "starts_with": text[chunk.start : chunk.start + 80],
                                "ends_with": text[max(chunk.start, chunk.end - 80) : chunk.end],
                            }
                            for chunk in holders
                        ],
                    }
                )

            if isinstance(run.chunker, SemanticChunker):
                entry["semantic"] = _semantic_boundaries(run.chunker, texts, question)

            study["strategies"][label] = entry

        studies.append(study)

    return studies


def _semantic_boundaries(chunker: SemanticChunker, texts: dict[str, str], question: Question) -> dict:
    """The sentence-to-sentence distances around the evidence, and the threshold."""
    document_id = question.evidence[0].document_id
    text = texts[document_id]
    analysis = chunker.analyze(text)
    start = min(passage.start for passage in question.evidence if passage.document_id == document_id)
    end = max(passage.end for passage in question.evidence if passage.document_id == document_id)
    indexes = [
        index
        for index, (sentence_start, sentence_end) in enumerate(analysis.sentences)
        if sentence_end > start and sentence_start < end
    ]
    first = max(min(indexes) - 2, 0)
    last = min(max(indexes) + 2, len(analysis.sentences) - 1)

    return {
        "threshold": analysis.threshold,
        "sentences": [
            {
                "index": index,
                "text": text[analysis.sentences[index][0] : analysis.sentences[index][1]],
                "in_evidence": index in indexes,
                "distance_to_next": (
                    analysis.distances[index] if index < len(analysis.distances) else None
                ),
                "breakpoint_after": index in analysis.breakpoints,
            }
            for index in range(first, last + 1)
        ],
    }


def _span(chunk: Chunk) -> TextSpan:
    return TextSpan(chunk.document_id, chunk.start, chunk.end)


def _delivered_span(result: SearchResult, by_id: dict[str, Chunk]) -> TextSpan:
    chunk = by_id[result.chunk_id]
    if "matched_text" in result.metadata and chunk.context_id:
        return _span(by_id[chunk.context_id])
    return _span(chunk)


def _chunk_record(chunk: Chunk) -> dict[str, Any]:
    return {
        "chunk_id": chunk.chunk_id,
        "document_id": chunk.document_id,
        "filename": chunk.metadata.get("filename"),
        "strategy": chunk.strategy,
        "start": chunk.start,
        "end": chunk.end,
        "level": chunk.level,
        "parent_id": chunk.parent_id,
        "context_id": chunk.context_id,
        "retrievable": chunk.retrievable,
        "section_path": chunk.metadata.get("section_path"),
        "chars": len(chunk.text),
        "text": chunk.text,
    }


def _config_record(config: ExperimentConfig) -> dict[str, Any]:
    record = asdict(config)
    for key in ("corpus_dir", "questions_path", "output_dir"):
        record[key] = str(record[key]).replace("\\", "/")
    return record


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
    )
