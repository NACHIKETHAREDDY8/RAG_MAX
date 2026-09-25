import config
from src.container import build_container
from src.repositories.vector_store_repository import VectorStoreRepository


def test_build_container_shares_one_repository(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(config, "VECTOR_STORE_PATH", tmp_path / "store.faiss")

    container = build_container()

    retrieval = container.rag_service.retrieval_service
    indexing = container.indexing_service
    assert isinstance(indexing.repository, VectorStoreRepository)
    assert retrieval.repository is indexing.repository
    assert retrieval.embedding_service is indexing.embedding_service
    assert retrieval.top_k == config.TOP_K
    assert indexing.repository.path == tmp_path / "store.faiss"
    assert indexing.count() == 0
