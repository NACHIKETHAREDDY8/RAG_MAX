import pytest

from src.vector_store.base import VectorStore
from src.vector_store.faiss_store import FAISSVectorStore
from src.vector_store.models import VectorRecord


def make_record(chunk_id: str, embedding: list[float]) -> VectorRecord:
    return VectorRecord(
        chunk_id=chunk_id,
        text=f"text of {chunk_id}",
        embedding=embedding,
        metadata={"source": "doc.pdf", "page": 1},
    )


def test_faiss_store_implements_interface():
    assert isinstance(FAISSVectorStore(dimension=3), VectorStore)


def test_search_returns_most_similar_first():
    store = FAISSVectorStore(dimension=3)
    store.add_many(
        [
            make_record("a", [1.0, 0.0, 0.0]),
            make_record("b", [0.0, 1.0, 0.0]),
        ]
    )

    results = store.search([0.9, 0.1, 0.0], top_k=2)

    assert [result.chunk_id for result in results] == ["a", "b"]
    assert results[0].score > results[1].score


def test_search_empty_store_raises():
    with pytest.raises(ValueError, match="empty vector index"):
        FAISSVectorStore(dimension=3).search([1.0, 0.0, 0.0])


def test_save_and_load_round_trip(tmp_path):
    path = tmp_path / "store.faiss"
    store = FAISSVectorStore(dimension=3)
    store.add(make_record("a", [1.0, 0.0, 0.0]))

    store.save(path)
    loaded = FAISSVectorStore.load(path)

    assert loaded.count() == 1
    assert loaded.list_records()[0].chunk_id == "a"
    assert loaded.search([1.0, 0.0, 0.0], top_k=1)[0].chunk_id == "a"


def test_load_or_create_starts_empty_without_files(tmp_path):
    store = FAISSVectorStore.load_or_create(tmp_path / "missing.faiss", dimension=3)

    assert store.count() == 0
    assert store.dimension == 3


def test_load_or_create_restores_saved_store(tmp_path):
    path = tmp_path / "store.faiss"
    store = FAISSVectorStore(dimension=3)
    store.add(make_record("a", [1.0, 0.0, 0.0]))
    store.save(path)

    assert FAISSVectorStore.load_or_create(path, dimension=3).count() == 1
