import pytest

from src.retrieval.service import RetrievalService
from src.tests.conftest import make_chunk


@pytest.fixture
def filled_repository(repository, embedding_service):
    chunks = [
        make_chunk("doc", 0, "cat cat cat"),
        make_chunk("doc", 1, "dog dog dog"),
        make_chunk("doc", 2, "fish fish fish"),
    ]
    repository.add_chunks(chunks, embedding_service.embed_chunks(chunks))
    return repository


def test_retrieve_returns_top_k_most_similar(embedding_service, filled_repository):
    service = RetrievalService(embedding_service, filled_repository, top_k=2)

    results = service.retrieve("tell me about the dog")

    assert len(results) == 2
    assert results[0].chunk_id == "doc_chunk_1"


def test_retrieve_top_k_argument_overrides_default(embedding_service, filled_repository):
    service = RetrievalService(embedding_service, filled_repository, top_k=2)

    assert len(service.retrieve("cat", top_k=1)) == 1


def test_retrieve_rejects_empty_question(embedding_service, filled_repository):
    service = RetrievalService(embedding_service, filled_repository)

    with pytest.raises(ValueError):
        service.retrieve("   ")


def test_retrieve_rejects_zero_top_k(embedding_service, filled_repository):
    service = RetrievalService(embedding_service, filled_repository)

    with pytest.raises(ValueError, match="top_k"):
        service.retrieve("cat", top_k=0)


def test_retrieval_does_not_load_faiss():
    import subprocess
    import sys
    from pathlib import Path

    code = (
        "import sys; import src.services.rag_service; "
        "sys.exit('faiss' in sys.modules)"
    )
    project_root = Path(__file__).resolve().parents[2]
    result = subprocess.run([sys.executable, "-c", code], cwd=project_root)
    assert result.returncode == 0
