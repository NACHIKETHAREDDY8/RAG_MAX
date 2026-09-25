import pytest

from src.chunking.models import Chunk
from src.repositories.vector_store_repository import VectorStoreRepository
from src.vector_store.faiss_store import FAISSVectorStore
from src.vector_store.models import VectorRecord


def make_chunk(document_id: str, index: int) -> Chunk:
    return Chunk(
        chunk_id=f"{document_id}_chunk_{index}",
        document_id=document_id,
        text=f"chunk {index}",
        chunk_index=index,
        metadata={"source": "doc.pdf", "page": 1},
    )


def test_add_chunks_stores_records_with_document_id(tmp_path):
    repository = VectorStoreRepository(FAISSVectorStore(dimension=2), tmp_path / "s.faiss")

    repository.add_chunks([make_chunk("doc-1", 0)], [[1.0, 0.0]])

    result = repository.search([1.0, 0.0], top_k=1)[0]
    assert result.chunk_id == "doc-1_chunk_0"
    assert result.metadata == {"source": "doc.pdf", "page": 1, "document_id": "doc-1"}
    assert repository.document_ids() == {"doc-1"}
    assert repository.count() == 1


def test_add_chunks_rejects_mismatched_embeddings(tmp_path):
    repository = VectorStoreRepository(FAISSVectorStore(dimension=2), tmp_path / "s.faiss")

    with pytest.raises(ValueError):
        repository.add_chunks([make_chunk("doc-1", 0)], [])


def test_document_ids_supports_records_without_document_id(tmp_path):
    store = FAISSVectorStore(dimension=2)
    store.add(
        VectorRecord(
            chunk_id="abc-1_chunk_3",
            text="old",
            embedding=[1.0, 0.0],
            metadata={"source": "doc.pdf", "page": 1},
        )
    )

    repository = VectorStoreRepository(store, tmp_path / "s.faiss")

    assert repository.document_ids() == {"abc-1"}


def test_save_persists_to_repository_path(tmp_path):
    path = tmp_path / "s.faiss"
    repository = VectorStoreRepository(FAISSVectorStore(dimension=2), path)
    repository.add_chunks([make_chunk("doc-1", 0)], [[1.0, 0.0]])

    repository.save()

    assert FAISSVectorStore.load(path).count() == 1
