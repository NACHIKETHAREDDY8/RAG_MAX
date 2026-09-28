"""The chunking experiment framework: evidence, metrics, caching and a full offline run."""

import json

import pytest

from src.embeddings.cache import CachedEmbeddingProvider
from src.experiments.chunking.dataset import EvidenceSpan, Question, load_questions
from src.experiments.chunking.metrics import (
    TextSpan,
    covered_chars,
    is_relevant,
    question_metrics,
)
from src.experiments.chunking.offline import HashingEmbeddingProvider
from src.experiments.chunking.runner import ExperimentConfig, StrategySpec, run_experiment
from src.ingestion.models import Document
from src.tests.conftest import FakeEmbeddingProvider

EVIDENCE = (EvidenceSpan("doc", 100, 200, "x" * 100), EvidenceSpan("doc", 300, 340, "y" * 40))
QUESTION = Question("q1", "?", "file.txt", EVIDENCE)


def test_relevance_needs_half_the_passage_or_half_the_chunk():
    assert is_relevant(TextSpan("doc", 50, 160), EVIDENCE)  # 60% of passage
    assert not is_relevant(TextSpan("doc", 0, 140), EVIDENCE)  # 40% of passage, 29% of chunk
    assert is_relevant(TextSpan("doc", 120, 150), EVIDENCE)  # small chunk inside passage
    assert not is_relevant(TextSpan("other", 100, 200), EVIDENCE)


def test_covered_chars_counts_overlapping_spans_once():
    spans = [TextSpan("doc", 90, 150), TextSpan("doc", 140, 170), TextSpan("doc", 190, 400)]

    assert covered_chars(EVIDENCE[0], spans) == 80


def test_question_metrics():
    retrieved = [TextSpan("doc", 0, 50), TextSpan("doc", 100, 200), TextSpan("doc", 290, 330)]
    delivered = retrieved

    metrics = question_metrics(QUESTION, retrieved, delivered)

    assert metrics["precision"] == pytest.approx(2 / 3)
    assert metrics["hit"] == 1.0
    assert metrics["reciprocal_rank"] == 0.5
    assert metrics["evidence_recall"] == 0.5  # second passage only 75% present
    assert metrics["completeness"] == pytest.approx(130 / 140)
    assert metrics["complete_answer"] == 0.0
    assert metrics["context_chars"] == 190


def test_question_metrics_with_nothing_retrieved():
    metrics = question_metrics(QUESTION, [], [])

    assert metrics["precision"] == metrics["reciprocal_rank"] == metrics["completeness"] == 0.0


def test_load_questions_locates_passages_and_rejects_typos(tmp_path):
    document = Document("d-1", "a.txt", "a.txt", None, "Alpha beta. Gamma delta.")
    path = tmp_path / "questions.json"
    path.write_text(
        json.dumps({"questions": [{"id": "q", "question": "?", "document": "a.txt", "evidence": ["Gamma delta."]}]}),
        encoding="utf-8",
    )

    [question] = load_questions(path, [document])
    assert question.evidence[0] == EvidenceSpan("d-1", 12, 24, "Gamma delta.")

    path.write_text(
        json.dumps({"questions": [{"id": "q", "question": "?", "document": "a.txt", "evidence": ["Gamma  delta."]}]}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="passage not found"):
        load_questions(path, [document])


def test_cached_provider_embeds_each_text_once_and_persists(tmp_path):
    inner = FakeEmbeddingProvider()
    path = tmp_path / "cache.npz"
    cache = CachedEmbeddingProvider(inner, namespace="fake", path=path)

    first = cache.embed_batch(["cat", "dog", "cat"])
    cache.embed_batch(["dog"])

    assert inner.calls == [["cat", "dog"]]
    assert (cache.misses, cache.hits) == (2, 2)

    reloaded = CachedEmbeddingProvider(FakeEmbeddingProvider(), namespace="fake", path=path)
    assert reloaded.embed_batch(["cat"])[0] == pytest.approx(first[0])
    assert reloaded.provider.calls == []

    other_model = CachedEmbeddingProvider(FakeEmbeddingProvider(), namespace="other", path=path)
    other_model.embed("cat")
    assert other_model.provider.calls == [["cat"]]


def test_offline_run_writes_every_output(tmp_path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "pets.txt").write_text(
        "Cats sleep most of the day and like warm windows. " * 6
        + "Dogs need a walk every morning and evening. " * 6
        + "Fish live in a tank and eat flakes twice a day. " * 6,
        encoding="utf-8",
    )
    (corpus / "guide.md").write_text(
        "# Guide\n\n## Feeding\n\nFeed the fish twice a day.\n\n## Walking\n\nWalk the dog every morning.\n",
        encoding="utf-8",
    )
    questions = tmp_path / "questions.json"
    questions.write_text(
        json.dumps(
            {
                "questions": [
                    {"id": "q1", "question": "How often do fish eat?", "document": "guide.md", "evidence": ["Feed the fish twice a day."]},
                    {"id": "q2", "question": "When do dogs need a walk?", "document": "pets.txt", "evidence": ["Dogs need a walk every morning and evening."]},
                ]
            }
        ),
        encoding="utf-8",
    )
    config = ExperimentConfig(
        name="test",
        corpus_dir=corpus,
        questions_path=questions,
        output_dir=tmp_path / "results",
        embedding_model="hashing",
        strategies=[
            StrategySpec("fixed", "fixed", {"chunk_size": 120, "overlap": 20}),
            StrategySpec("semantic", "semantic", {"max_chars": 400, "min_chars": 50}),
            StrategySpec("parent_child", "parent_child", {"parent_size": 400, "child_size": 100}),
        ],
        top_k=2,
        ks=[1, 2],
        case_studies=[{"question": "q2", "strategies": ["fixed", "semantic", "missing"]}],
    )

    summary = run_experiment(config, HashingEmbeddingProvider(64), 64, log=lambda _: None)

    run_dir = tmp_path / "results" / "test"
    for name in ("config.json", "summary.json", "case_studies.json", "report.md"):
        assert (run_dir / name).exists()
    for label in ("fixed", "semantic", "parent_child"):
        for name in ("config.json", "chunks.jsonl", "retrieval.json", "metrics.json", "index.faiss", "index.faiss.json"):
            assert (run_dir / label / name).exists(), f"{label}/{name}"

    strategies = summary["strategies"]
    assert set(strategies) == {"fixed", "semantic", "parent_child"}
    assert strategies["parent_child"]["stats"]["context_chunks"] > 0
    assert strategies["semantic"]["stats"]["embedded_texts"] > strategies["semantic"]["stats"]["chunks"]
    for values in strategies.values():
        assert set(values["metrics"]) == {"1", "2"}
        assert 0.0 <= values["metrics"]["2"]["completeness"] <= 1.0

    case_studies = json.loads((run_dir / "case_studies.json").read_text(encoding="utf-8"))
    assert set(case_studies[0]["strategies"]) == {"fixed", "semantic"}
    assert "semantic" in case_studies[0]["strategies"]["semantic"]
    report = (run_dir / "report.md").read_text(encoding="utf-8")
    assert "## Results at k = 2" in report and "q2: When do dogs need a walk?" in report


def test_config_file_round_trip(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "name": "x",
                "corpus_dir": "c",
                "questions": "q.json",
                "output_dir": "out",
                "embedding_model": "m",
                "top_k": 4,
                "ks": [1],
                "strategies": {"a": {"strategy": "fixed"}, "b": {"strategy": "recursive", "params": {"chunk_size": 9}}},
            }
        ),
        encoding="utf-8",
    )

    config = ExperimentConfig.from_file(path)

    assert config.ks == [1, 4]
    assert [(spec.label, spec.strategy, spec.params) for spec in config.strategies] == [
        ("a", "fixed", {}),
        ("b", "recursive", {"chunk_size": 9}),
    ]
