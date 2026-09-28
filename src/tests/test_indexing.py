from src.indexing.service import IndexingService
from src.tests.conftest import make_chunk, make_document


def test_index_chunks_embeds_and_stores(embedding_service, repository):
    service = IndexingService(embedding_service, repository)

    service.index_chunks([make_chunk("doc", 0, "cat"), make_chunk("doc", 1, "dog")])

    assert repository.count() == 2
    assert repository.search([0.0, 1.0, 0.0], top_k=1)[0].chunk_id == "doc_chunk_1"


def test_index_document_chunks_with_page_metadata(embedding_service, repository):
    service = IndexingService(embedding_service, repository, chunk_size=10, chunk_overlap=2)

    added = service.index_document(make_document("cat dog fish cat dog"))

    assert added == 3
    record = repository.vector_store.list_records()[0]
    assert record.chunk_id == "default:hash-1_chunk_0"
    assert record.metadata == {
        "file_size": 10,
        "source_type": "pdf",
        "version": 1,
        "tenant_id": "default",
        "document_id": "hash-1",
        "filename": "animals.pdf",
        "page": 2,
    }


def test_index_document_skips_already_indexed(
    embedding_service, embedding_provider, repository
):
    service = IndexingService(embedding_service, repository)
    document = make_document("cat")

    assert service.index_document(document) == 1
    assert service.index_document(document) == 0
    assert service.is_indexed("hash-1")
    assert len(embedding_provider.calls) == 1
    assert service.count() == 1
