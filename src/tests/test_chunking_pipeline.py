"""A chosen chunker flowing through indexing, storage, refresh and retrieval."""

import os

import pytest

import config
from src.chunking.parent_child import ParentChildChunker
from src.chunking.registry import get_chunker
from src.chunking.semantic import SemanticChunker
from src.container import build_container
from src.indexing.service import IndexingService
from src.retrieval.service import RetrievalService, expand_to_context
from src.tests.conftest import make_document
from src.vector_store.models import SearchResult

TEXT = (
    "The cat sleeps all day. The cat likes warm places.\n\n"
    "The dog barks at night. The dog guards the house.\n\n"
    "The fish swims in circles. The fish eats flakes."
)


def test_indexing_embeds_only_children_and_stores_their_parent(
    embedding_service, embedding_provider, repository
):
    chunker = ParentChildChunker(parent_size=110, child_size=55)
    service = IndexingService(embedding_service, repository, chunker=chunker)

    chunks = service.chunk_and_index(make_document(TEXT))

    children = [chunk for chunk in chunks if chunk.retrievable]
    assert repository.count() == len(children) < len(chunks)
    assert sum(len(batch) for batch in embedding_provider.calls) == len(children)
    record = repository.vector_store.list_records()[0]
    assert record.metadata["chunk_strategy"] == "parent_child"
    assert record.metadata["parent_id"] == "default:hash-1_parent_0"
    assert record.metadata["context_id"] == "default:hash-1_parent_0"
    assert record.metadata["context_text"].startswith("The cat sleeps all day.")
    assert (record.metadata["chunk_start"], record.metadata["chunk_level"]) == (0, 1)


def test_index_document_counts_retrievable_chunks(embedding_service, repository):
    service = IndexingService(
        embedding_service, repository, chunker=ParentChildChunker(parent_size=110, child_size=55)
    )

    added = service.index_document(make_document(TEXT))

    assert added == repository.count()
    assert service.index_document(make_document(TEXT)) == 0


def test_refresh_metadata_keeps_what_the_chunker_recorded(embedding_service, repository):
    service = IndexingService(
        embedding_service, repository, chunker=ParentChildChunker(parent_size=110, child_size=55)
    )
    document = make_document(TEXT)
    service.index_document(document)
    before = repository.vector_store.list_records()[0].metadata

    document.metadata["department"] = "Pets"
    assert service.refresh_metadata(document) == repository.count()
    assert service.refresh_metadata(document) == 0

    after = repository.vector_store.list_records()[0].metadata
    assert after == {**before, "department": "Pets"}


def test_retrieval_expands_children_to_their_parent_once(embedding_service, repository):
    service = IndexingService(
        embedding_service, repository, chunker=ParentChildChunker(parent_size=110, child_size=30)
    )
    service.index_document(make_document(TEXT))
    retrieval = RetrievalService(embedding_service, repository, top_k=2, expand_context=True)

    results = retrieval.retrieve("cat")

    # Both cat children match; they share one parent, delivered once.
    assert len(results) == 1
    assert results[0].text.startswith("The cat sleeps all day.")
    assert "cat" in results[0].metadata["matched_text"]
    assert "context_text" not in results[0].metadata


def test_retrieval_without_expansion_returns_the_matched_chunks(embedding_service, repository):
    service = IndexingService(
        embedding_service, repository, chunker=ParentChildChunker(parent_size=110, child_size=30)
    )
    service.index_document(make_document(TEXT))

    results = RetrievalService(embedding_service, repository, top_k=2).retrieve("cat")

    assert len(results) == 2
    assert all(len(result.text) <= 30 for result in results)


def test_expand_to_context_passes_plain_results_through():
    plain = SearchResult("a", "text", {"filename": "f"}, 0.9)

    assert expand_to_context([plain]) == [plain]


def test_semantic_chunker_indexes_through_the_same_pipeline(embedding_service, repository):
    chunker = SemanticChunker(embedding_service, buffer_size=0, threshold_type="absolute", breakpoint_threshold=0.5, min_chars=0)
    service = IndexingService(embedding_service, repository, chunker=chunker)

    service.index_document(make_document(TEXT))

    texts = sorted(record.text for record in repository.vector_store.list_records())
    assert texts == [
        "The cat sleeps all day. The cat likes warm places.",
        "The dog barks at night. The dog guards the house.",
        "The fish swims in circles. The fish eats flakes.",
    ]


def test_container_builds_the_configured_strategy(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(config, "VECTOR_STORE_PATH", tmp_path / "store.faiss")
    monkeypatch.setattr(config, "CHUNKING_STRATEGY", "parent_child")

    container = build_container()

    assert isinstance(container.indexing_service.chunker, ParentChildChunker)
    assert container.indexing_service.chunker.parent_size == config.CHUNKING_PARAMS["parent_child"]["parent_size"]
    assert container.rag_service.retrieval_service.expand_context


def test_container_semantic_strategy_shares_the_embedding_service(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(config, "VECTOR_STORE_PATH", tmp_path / "store.faiss")
    monkeypatch.setattr(config, "CHUNKING_STRATEGY", "semantic")

    container = build_container()

    chunker = container.indexing_service.chunker
    assert isinstance(chunker, SemanticChunker)
    assert chunker.embedding_service is container.indexing_service.embedding_service
    assert not container.rag_service.retrieval_service.expand_context


@pytest.mark.skipif(
    os.getenv("CHUNKING_STRATEGY", "fixed") != "fixed",
    reason="CHUNKING_STRATEGY is set in the environment",
)
def test_default_configuration_keeps_fixed_chunks_and_index_name():
    assert config.CHUNKING_STRATEGY == "fixed"
    assert str(config.VECTOR_STORE_PATH) == "vector_store.faiss"
    chunker = get_chunker(config.CHUNKING_STRATEGY, **config.CHUNKING_PARAMS["fixed"])
    assert (chunker.chunk_size, chunker.overlap) == (config.CHUNK_SIZE, config.CHUNK_OVERLAP)


def test_index_path_changes_with_strategy_and_parameters():
    legacy = config.vector_store_path("fixed", {"chunk_size": 500, "overlap": 50})
    resized = config.vector_store_path("fixed", {"chunk_size": 800, "overlap": 50})
    semantic = config.vector_store_path("semantic", {"max_chars": 1000})

    assert str(legacy) == "vector_store.faiss"
    assert resized.name.startswith("vector_store.fixed-") and resized != legacy
    assert semantic.name.startswith("vector_store.semantic-")
    assert semantic != config.vector_store_path("semantic", {"max_chars": 900})
    assert semantic == config.vector_store_path("semantic", {"max_chars": 1000})


def test_container_rejects_a_strategy_without_params(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(config, "VECTOR_STORE_PATH", tmp_path / "store.faiss")
    monkeypatch.setattr(config, "CHUNKING_STRATEGY", "markdown")

    with pytest.raises(ValueError, match="Use one of: fixed, hierarchical"):
        build_container()
