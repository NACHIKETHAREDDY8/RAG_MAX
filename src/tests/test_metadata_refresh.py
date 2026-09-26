import pytest

import app
import config
from src.indexing.service import IndexingService
from src.retrieval.service import RetrievalService
from src.tests.conftest import make_document
from src.vector_store.faiss_store import FAISSVectorStore
from src.vector_store.models import VectorRecord


def add_legacy_record(repository, embedding_service, filename="animals.pdf"):
    """Store a chunk shaped like one indexed before metadata filtering."""
    repository.vector_store.add(
        VectorRecord(
            chunk_id="hash-1_chunk_0",
            text="cat",
            embedding=embedding_service.embed_text("cat"),
            metadata={"file_size": 10, "file_type": ".pdf", "source": filename, "page": 2},
        )
    )


def stored_metadata(repository) -> dict:
    return repository.vector_store.list_records()[0].metadata


def test_refresh_upgrades_legacy_chunks_without_embedding(
    embedding_service, embedding_provider, repository
):
    add_legacy_record(repository, embedding_service)
    service = IndexingService(embedding_service, repository)
    document = make_document("cat")
    embedding_calls = len(embedding_provider.calls)

    assert service.index_document(document) == 0
    assert service.refresh_metadata(document) == 1

    assert len(embedding_provider.calls) == embedding_calls
    assert repository.count() == 1
    assert stored_metadata(repository) == {
        "file_size": 10,
        "source_type": "pdf",
        "tenant_id": "default",
        "document_id": "hash-1",
        "filename": "animals.pdf",
        "page": 2,
    }
    retrieval = RetrievalService(embedding_service, repository)
    assert len(retrieval.retrieve("cat", filters={"tenant_id": "default"})) == 1


def test_refresh_is_idempotent(embedding_service, repository):
    add_legacy_record(repository, embedding_service)
    service = IndexingService(embedding_service, repository)

    assert service.refresh_metadata(make_document("cat")) == 1
    assert service.refresh_metadata(make_document("cat")) == 0


def test_refresh_picks_up_edited_metadata(embedding_service, repository):
    service = IndexingService(embedding_service, repository)
    document = make_document("cat")
    document.metadata["department"] = "HR"
    service.index_document(document)

    document.metadata["department"] = "Finance"

    assert service.index_document(document) == 0
    assert service.refresh_metadata(document) == 1
    assert stored_metadata(repository)["department"] == "Finance"


def test_first_tenant_adopts_legacy_chunks(
    embedding_service, embedding_provider, repository
):
    add_legacy_record(repository, embedding_service)
    service = IndexingService(embedding_service, repository)
    for_a = make_document("cat")
    for_a.metadata["tenant_id"] = "company_A"
    embedding_calls = len(embedding_provider.calls)

    assert service.index_document(for_a) == 0
    assert service.refresh_metadata(for_a) == 1
    assert len(embedding_provider.calls) == embedding_calls

    # Once owned by company_A, another tenant gets its own embedded copy.
    for_b = make_document("cat")
    for_b.metadata["tenant_id"] = "company_B"
    assert service.index_document(for_b) == 1

    retrieval = RetrievalService(embedding_service, repository)
    tenant_a = retrieval.retrieve("cat", filters={"tenant_id": "company_A"})
    assert [result.chunk_id for result in tenant_a] == ["hash-1_chunk_0"]
    assert len(retrieval.retrieve("cat", filters={"tenant_id": "company_B"})) == 1


def test_refresh_leaves_identical_file_under_other_name(embedding_service, repository):
    add_legacy_record(repository, embedding_service, filename="original.pdf")
    service = IndexingService(embedding_service, repository)
    copy = make_document("cat")  # same content hash, filename animals.pdf

    assert service.index_document(copy) == 0
    assert service.refresh_metadata(copy) == 0
    assert stored_metadata(repository)["source"] == "original.pdf"


def test_update_metadata_requires_exactly_one_record():
    store = FAISSVectorStore(dimension=2)
    store.add(VectorRecord("a", "a", [1.0, 0.0], {"page": 1}))

    store.update_metadata("a", {"page": 2})

    assert store.list_records()[0].metadata == {"page": 2}
    with pytest.raises(KeyError):
        store.update_metadata("missing", {})


def test_update_metadata_survives_save_and_load(tmp_path):
    path = tmp_path / "store.faiss"
    store = FAISSVectorStore(dimension=2)
    store.add(VectorRecord("a", "a", [1.0, 0.0], {"page": 1}))
    store.update_metadata("a", {"page": 1, "tenant_id": "company_A"})
    store.save(path)

    loaded = FAISSVectorStore.load(path)

    assert loaded.search([1.0, 0.0], filters={"tenant_id": "company_A"})[0].chunk_id == "a"


@pytest.fixture
def one_pdf_folder(monkeypatch, tmp_path):
    documents_dir = tmp_path / "documents"
    documents_dir.mkdir()
    (documents_dir / "animals.pdf").write_bytes(b"")
    monkeypatch.setattr(config, "DOCUMENTS_DIR", documents_dir)
    monkeypatch.setattr(app, "ingest_pdf", lambda _: [make_document("cat")])


def test_index_documents_saves_refreshed_metadata(
    one_pdf_folder, capsys, embedding_service, repository
):
    add_legacy_record(repository, embedding_service)

    app.index_documents(IndexingService(embedding_service, repository))

    assert "Updated metadata of page 2" in capsys.readouterr().out
    assert FAISSVectorStore.load(repository.path).list_records()[0].metadata[
        "tenant_id"
    ] == "default"


def test_index_documents_does_not_save_when_nothing_changed(
    one_pdf_folder, capsys, embedding_service, repository
):
    service = IndexingService(embedding_service, repository)
    service.index_document(make_document("cat"))

    app.index_documents(service)

    assert "Already indexed, skipping page 2" in capsys.readouterr().out
    assert not repository.path.exists()
