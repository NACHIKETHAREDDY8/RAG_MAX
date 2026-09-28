import pytest

import app
import config
from src.indexing.service import IndexingService
from src.ingestion.models import Document
from src.ingestion.pipeline import IngestionPipeline
from src.retrieval.service import RetrievalService
from src.vector_store.faiss_store import FAISSVectorStore
from src.vector_store.models import VectorRecord


def version_of(file_key: str, text: str, filename="policy.txt", page=None, tenant=None) -> Document:
    metadata = {"source_type": "txt"}
    if tenant:
        metadata["tenant_id"] = tenant
    return Document(
        document_id=f"{file_key}-{page or 1}",
        source=f"documents/{filename}",
        filename=filename,
        page_number=page,
        text=text,
        metadata=metadata,
    )


def stored(repository) -> list[tuple[str, dict]]:
    return [
        (record.text, record.metadata)
        for record in repository.vector_store.list_records()
    ]


# --- version numbers -----------------------------------------------------------


def test_first_version_is_1(embedding_service, repository):
    IndexingService(embedding_service, repository).index_document(version_of("aaaa", "cat"))

    (_, metadata), = stored(repository)
    assert metadata["version"] == 1
    assert "previous_version" not in metadata


def test_edited_file_replaces_the_previous_version(embedding_service, repository):
    service = IndexingService(embedding_service, repository)
    service.index_document(version_of("aaaa", "cat"))

    assert service.index_document(version_of("bbbb", "dog")) == 1

    (text, metadata), = stored(repository)
    assert text == "dog"
    assert metadata["version"] == 2
    assert metadata["previous_version"] == "aaaa"
    retrieval = RetrievalService(embedding_service, repository)
    assert [result.text for result in retrieval.retrieve("cat")] == ["dog"]


def test_versions_keep_counting(embedding_service, repository):
    service = IndexingService(embedding_service, repository)
    for key, text in [("aaaa", "cat"), ("bbbb", "dog"), ("cccc", "fish"), ("aaaa", "cat")]:
        service.index_document(version_of(key, text))

    (text, metadata), = stored(repository)
    # Going back to the first content is a new version, not a restore.
    assert (text, metadata["version"], metadata["previous_version"]) == ("cat", 4, "cccc")


def test_every_page_of_a_new_version_shares_its_version(embedding_service, repository):
    service = IndexingService(embedding_service, repository)
    service.index_document(version_of("aaaa", "cat", filename="a.pdf", page=1))
    service.index_document(version_of("aaaa", "cat", filename="a.pdf", page=2))

    service.index_document(version_of("bbbb", "dog", filename="a.pdf", page=1))
    service.index_document(version_of("bbbb", "fish", filename="a.pdf", page=2))

    assert [(text, metadata["page"], metadata["version"]) for text, metadata in stored(repository)] == [
        ("dog", 1, 2),
        ("fish", 2, 2),
    ]


def test_versions_are_tracked_per_filename(embedding_service, repository):
    service = IndexingService(embedding_service, repository)
    service.index_document(version_of("aaaa", "cat", filename="a.txt"))
    service.index_document(version_of("bbbb", "dog", filename="b.txt"))

    assert [(text, metadata["version"]) for text, metadata in stored(repository)] == [
        ("cat", 1),
        ("dog", 1),
    ]


def test_versions_are_tracked_per_tenant(embedding_service, repository):
    service = IndexingService(embedding_service, repository)
    service.index_document(version_of("aaaa", "cat", tenant="company_A"))
    service.index_document(version_of("bbbb", "dog", tenant="company_B"))

    assert [
        (metadata["tenant_id"], metadata["version"]) for _, metadata in stored(repository)
    ] == [("company_A", 1), ("company_B", 1)]


def test_refresh_keeps_version_stable(embedding_service, repository):
    service = IndexingService(embedding_service, repository)
    service.index_document(version_of("aaaa", "cat"))
    service.index_document(version_of("bbbb", "dog"))

    assert service.refresh_metadata(version_of("bbbb", "dog")) == 0


def test_chunks_from_before_versioning_count_as_version_1(embedding_service, repository):
    repository.vector_store.add(
        VectorRecord(
            chunk_id="default:aaaa-1_chunk_0",
            text="cat",
            embedding=embedding_service.embed_text("cat"),
            metadata={"document_id": "aaaa-1", "filename": "policy.txt", "tenant_id": "default"},
        )
    )
    service = IndexingService(embedding_service, repository)

    assert service.refresh_metadata(version_of("aaaa", "cat")) == 1
    assert stored(repository)[0][1]["version"] == 1

    service.index_document(version_of("bbbb", "dog"))
    assert [(text, metadata["version"]) for text, metadata in stored(repository)] == [("dog", 2)]


def test_non_paginated_documents_have_no_page(embedding_service, repository):
    IndexingService(embedding_service, repository).index_document(version_of("aaaa", "cat"))

    assert "page" not in stored(repository)[0][1]


def test_editing_a_file_on_disk_replaces_it_on_the_next_run(
    monkeypatch, tmp_path, embedding_service, repository
):
    documents_dir = tmp_path / "documents"
    documents_dir.mkdir()
    monkeypatch.setattr(config, "DOCUMENTS_DIR", documents_dir)
    path = documents_dir / "policy.txt"
    service = IndexingService(embedding_service, repository)

    path.write_text("cats get 10 days", encoding="utf-8")
    app.index_documents(service, IngestionPipeline())
    path.write_text("dogs get 20 days", encoding="utf-8")
    app.index_documents(service, IngestionPipeline())

    loaded = FAISSVectorStore.load(repository.path).list_records()
    assert [(record.text, record.metadata["version"]) for record in loaded] == [
        ("dogs get 20 days", 2)
    ]


# --- deleting from the store ---------------------------------------------------


def make_store() -> FAISSVectorStore:
    store = FAISSVectorStore(dimension=2)
    store.add_many(
        [
            VectorRecord("a", "a", [1.0, 0.0]),
            VectorRecord("b", "b", [0.0, 1.0]),
            VectorRecord("c", "c", [1.0, 1.0]),
        ]
    )
    return store


def test_delete_removes_records_and_keeps_search_aligned():
    store = make_store()

    assert store.delete(["a", "missing"]) == 1

    assert [record.chunk_id for record in store.list_records()] == ["b", "c"]
    assert store.index.ntotal == 2
    assert store.search([0.0, 1.0], top_k=1)[0].chunk_id == "b"
    assert store.search([1.0, 1.0], top_k=1)[0].chunk_id == "c"


def test_delete_nothing_is_a_no_op():
    store = make_store()

    assert store.delete([]) == 0
    assert store.count() == 3


def test_delete_survives_save_and_load(tmp_path):
    store = make_store()
    store.delete(["b"])
    store.save(tmp_path / "store.faiss")

    loaded = FAISSVectorStore.load(tmp_path / "store.faiss")

    assert [record.chunk_id for record in loaded.list_records()] == ["a", "c"]
    assert loaded.search([1.0, 0.0], top_k=1)[0].chunk_id == "a"


@pytest.mark.parametrize("filters", [{"tenant_id": "x"}, None])
def test_filtered_search_after_delete(filters):
    store = FAISSVectorStore(dimension=2)
    store.add_many(
        [
            VectorRecord("a", "a", [1.0, 0.0], {"tenant_id": "x"}),
            VectorRecord("b", "b", [1.0, 0.1], {"tenant_id": "x"}),
            VectorRecord("c", "c", [0.9, 0.2], {"tenant_id": "x"}),
        ]
    )

    store.delete(["a"])

    assert [result.chunk_id for result in store.search([1.0, 0.0], top_k=5, filters=filters)] == ["b", "c"]
