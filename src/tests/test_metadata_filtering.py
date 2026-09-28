import json

import pytest
from pypdf import PdfWriter

from src.chunking.models import Chunk
from src.generation.prompt import format_sources
from src.generation.service import GenerationService
from src.indexing.service import IndexingService
from src.ingestion.errors import MetadataError
from src.ingestion.models import ParsedDocument, ParsedSection
from src.ingestion.parsers.pdf_parser import PdfParser
from src.ingestion.pipeline import IngestionPipeline
from src.retrieval.service import RetrievalService
from src.services.rag_service import NO_CONTEXT_ANSWER, RAGService
from src.tests.conftest import FakeLLM, make_document
from src.vector_store.faiss_store import FAISSVectorStore
from src.vector_store.models import SearchResult, VectorRecord


def make_tagged_chunk(chunk_id: str, text: str, **metadata) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        document_id=f"doc-{chunk_id}",
        text=text,
        chunk_index=0,
        metadata={"filename": f"{chunk_id}.pdf", "page": 1, **metadata},
    )


# The fake embedder counts "cat", "dog" and "fish", and similarity is cosine,
# so the less "dog" a chunk mixes in, the closer it is to a "cat" question.
# For "cat" the ranking is: b_hr_policy > finance_policy > hr_handbook >
# hr_policy > hr_policy_2, regardless of metadata.
CORPUS = [
    make_tagged_chunk("hr_policy", "cat dog", department="HR", category="policy", tenant_id="company_A"),
    make_tagged_chunk("hr_policy_2", "cat dog dog", department="HR", category="policy", tenant_id="company_A"),
    make_tagged_chunk("hr_handbook", "cat cat dog", department="HR", category="handbook", tenant_id="company_A"),
    make_tagged_chunk("finance_policy", "cat cat cat dog", department="Finance", category="policy", tenant_id="company_A"),
    make_tagged_chunk("b_hr_policy", "cat", department="HR", category="policy", tenant_id="company_B"),
]


@pytest.fixture
def retrieval(embedding_service, repository) -> RetrievalService:
    repository.add_chunks(CORPUS, embedding_service.embed_chunks(CORPUS))
    return RetrievalService(embedding_service, repository, top_k=3)


def ids(results: list[SearchResult]) -> list[str]:
    return [result.chunk_id for result in results]


# --- search with filters -------------------------------------------------


def test_no_filter_searches_every_chunk(retrieval):
    results = retrieval.retrieve("cat", top_k=10)

    assert len(results) == len(CORPUS)
    assert results[0].chunk_id == "b_hr_policy"


def test_no_filter_matches_previous_behaviour(retrieval):
    expected = ids(retrieval.retrieve("cat dog"))

    assert ids(retrieval.retrieve("cat dog", filters=None)) == expected
    assert ids(retrieval.retrieve("cat dog", filters={})) == expected


def test_one_filter_only_returns_matching_chunks(retrieval):
    results = retrieval.retrieve("cat", top_k=10, filters={"department": "HR"})

    assert {result.metadata["department"] for result in results} == {"HR"}
    assert "finance_policy" not in ids(results)
    assert len(results) == 4


def test_multiple_filters_must_all_match(retrieval):
    results = retrieval.retrieve(
        "What is the leave policy? cat",
        top_k=10,
        filters={"department": "HR", "category": "policy", "tenant_id": "company_A"},
    )

    # hr_handbook and finance_policy are better semantic matches but each
    # fails one condition, so only the HR policy chunks come back, best first.
    assert ids(results) == ["hr_policy", "hr_policy_2"]
    assert results[0].score >= results[1].score


def test_no_matching_metadata_returns_empty_list(retrieval):
    assert retrieval.retrieve("cat", filters={"department": "Legal"}) == []
    assert retrieval.retrieve("cat", filters={"region": "EU"}) == []


def test_filter_on_missing_field_never_matches(embedding_service, repository):
    chunk = make_tagged_chunk("untagged", "cat")
    repository.add_chunks([chunk], embedding_service.embed_chunks([chunk]))
    service = RetrievalService(embedding_service, repository)

    assert service.retrieve("cat", filters={"tenant_id": "company_A"}) == []


def test_tenant_filter_isolates_tenants(retrieval):
    tenant_a = retrieval.retrieve("cat", top_k=10, filters={"tenant_id": "company_A"})
    tenant_b = retrieval.retrieve("cat", top_k=10, filters={"tenant_id": "company_B"})

    # company_B owns the best match for "cat", yet company_A never sees it.
    assert "b_hr_policy" not in ids(tenant_a)
    assert len(tenant_a) == 4
    assert ids(tenant_b) == ["b_hr_policy"]


def test_filtered_search_fills_top_k_from_matches(retrieval):
    # The two best "cat" matches overall are not HR/company_A; filtering
    # after the search would have left fewer than top_k results.
    results = retrieval.retrieve(
        "cat",
        top_k=2,
        filters={"department": "HR", "tenant_id": "company_A"},
    )

    assert ids(results) == ["hr_handbook", "hr_policy"]


def test_top_k_is_capped_by_matching_chunks(retrieval):
    assert len(retrieval.retrieve("cat", top_k=1, filters={"department": "HR"})) == 1
    assert len(retrieval.retrieve("cat", top_k=10, filters={"category": "handbook"})) == 1


def test_filters_must_be_a_mapping(retrieval):
    with pytest.raises(TypeError, match="filters"):
        retrieval.retrieve("cat", filters=[("department", "HR")])


def test_filtered_search_works_after_save_and_load(tmp_path):
    path = tmp_path / "store.faiss"
    store = FAISSVectorStore(dimension=2)
    store.add_many(
        [
            VectorRecord("a", "a", [1.0, 0.0], {"tenant_id": "company_A"}),
            VectorRecord("b", "b", [1.0, 0.1], {"tenant_id": "company_B"}),
        ]
    )
    store.save(path)

    results = FAISSVectorStore.load(path).search(
        [1.0, 0.1], top_k=5, filters={"tenant_id": "company_A"}
    )

    assert ids(results) == ["a"]
    assert results[0].metadata == {"tenant_id": "company_A"}


# --- metadata through indexing ---------------------------------------------


def test_index_document_stores_all_metadata(embedding_service, repository):
    document = make_document("cat")
    document.metadata.update(
        department="HR",
        category="policy",
        date="2026-01-15",
        author="Jane Doe",
        tenant_id="company_A",
    )

    IndexingService(embedding_service, repository).index_document(document)

    record = repository.vector_store.list_records()[0]
    assert record.metadata == {
        "file_size": 10,
        "source_type": "pdf",
        "department": "HR",
        "category": "policy",
        "date": "2026-01-15",
        "author": "Jane Doe",
        "version": 1,
        "tenant_id": "company_A",
        "document_id": "hash-1",
        "filename": "animals.pdf",
        "page": 2,
        "chunk_strategy": "fixed",
        "chunk_start": 0,
        "chunk_end": 3,
    }


def test_same_document_is_indexed_once_per_tenant(embedding_service, repository):
    service = IndexingService(embedding_service, repository)
    for_a = make_document("cat")
    for_a.metadata["tenant_id"] = "company_A"
    for_b = make_document("cat")
    for_b.metadata["tenant_id"] = "company_B"

    assert service.index_document(for_a) == 1
    assert service.index_document(for_a) == 0
    assert service.index_document(for_b) == 1

    retrieval = RetrievalService(embedding_service, repository)
    assert len(retrieval.retrieve("cat", filters={"tenant_id": "company_B"})) == 1

    chunk_ids = [record.chunk_id for record in repository.vector_store.list_records()]
    assert chunk_ids == ["company_A:hash-1_chunk_0", "company_B:hash-1_chunk_0"]
    assert repository.document_ids() == {"hash-1"}


def test_records_without_tenant_count_as_default_tenant(embedding_service, repository):
    legacy = make_tagged_chunk("legacy", "cat")
    legacy.document_id = "hash-1"
    repository.add_chunks([legacy], embedding_service.embed_chunks([legacy]))

    assert IndexingService(embedding_service, repository).index_document(
        make_document("cat")
    ) == 0


# --- metadata extraction during ingestion ----------------------------------


def write_pdf(path, **info) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    if info:
        writer.add_metadata(info)
    with open(path, "wb") as file:
        writer.write(file)


def test_parse_pdf_metadata_reads_author_and_date(tmp_path):
    path = tmp_path / "policy.pdf"
    write_pdf(path, **{"/Author": " Jane Doe ", "/CreationDate": "D:20260115093000Z"})

    assert PdfParser().parse(path).metadata == {
        "author": "Jane Doe",
        "date": "2026-01-15",
        "page_count": 1,
    }


def test_parse_pdf_metadata_ignores_unparseable_date(tmp_path):
    path = tmp_path / "policy.pdf"
    write_pdf(path, **{"/CreationDate": "yesterday"})

    assert PdfParser().parse(path).metadata == {"page_count": 1}


def test_sidecar_overrides_embedded_metadata(tmp_path):
    path = tmp_path / "policy.pdf"
    write_pdf(path, **{"/Author": "dell", "/CreationDate": "D:20260115093000Z"})
    (tmp_path / "policy.meta.json").write_text(
        json.dumps({"author": "HR Team", "department": "HR", "tenant_id": "company_A"}),
        encoding="utf-8",
    )

    metadata = IngestionPipeline().ingest(path).metadata

    assert metadata["author"] == "HR Team"
    assert metadata["date"] == "2026-01-15"
    assert metadata["department"] == "HR"
    assert metadata["tenant_id"] == "company_A"
    assert metadata["source_type"] == "pdf"


@pytest.mark.parametrize(
    ("sidecar", "message"),
    [
        ({"departmnet": "HR"}, "unsupported fields"),
        ({"page": "3"}, "unsupported fields"),
        ({"department": 7}, "must be a string"),
        (["HR"], "JSON object"),
    ],
)
def test_invalid_sidecar_is_rejected(tmp_path, sidecar, message):
    path = tmp_path / "policy.pdf"
    write_pdf(path)
    (tmp_path / "policy.meta.json").write_text(json.dumps(sidecar), encoding="utf-8")

    with pytest.raises(MetadataError, match=message):
        IngestionPipeline().ingest(path)


def test_ingest_pdf_gives_every_page_the_document_metadata(tmp_path, monkeypatch):
    path = tmp_path / "policy.pdf"
    write_pdf(path)
    (tmp_path / "policy.meta.json").write_text(
        json.dumps({"department": "HR", "category": "policy"}), encoding="utf-8"
    )
    monkeypatch.setattr(
        PdfParser,
        "_parse",
        lambda self, _: ParsedDocument(
            [
                ParsedSection("Leave policy", page_number=1),
                ParsedSection("More leave", page_number=2),
            ]
        ),
    )

    documents = IngestionPipeline().ingest(path).documents

    assert [document.page_number for document in documents] == [1, 2]
    for document in documents:
        assert document.metadata["department"] == "HR"
        assert document.metadata["category"] == "policy"
    assert documents[0].metadata is not documents[1].metadata


# --- source attribution ---------------------------------------------------


def test_search_result_exposes_source_fields():
    result = SearchResult(
        chunk_id="d_chunk_0",
        text="t",
        metadata={"filename": "leave.pdf", "page": 4, "document_id": "d"},
        score=1.0,
    )

    assert (result.filename, result.page, result.document_id) == ("leave.pdf", 4, "d")
    assert format_sources([result]) == [
        "d_chunk_0 | Source: leave.pdf | Page: 4 | Document: d"
    ]


def test_search_result_reads_filename_from_pre_phase_9_records():
    result = SearchResult("c", "t", {"source": "old.pdf", "page": 1}, 1.0)

    assert result.filename == "old.pdf"
    assert result.document_id is None


# --- full RAG flow --------------------------------------------------------


def test_rag_skips_llm_when_no_chunk_matches(retrieval):
    llm = FakeLLM()
    rag_service = RAGService(retrieval, GenerationService(llm))

    answer, context = rag_service.answer_with_context(
        "cat", filters={"department": "Legal"}
    )

    assert answer == NO_CONTEXT_ANSWER
    assert context == []
    assert llm.prompts == []


def test_rag_answers_from_filtered_context_with_sources(retrieval):
    llm = FakeLLM("Employees get 20 days of leave.")
    rag_service = RAGService(retrieval, GenerationService(llm))

    answer, context = rag_service.answer_with_context(
        "What is the leave policy? cat",
        top_k=10,
        filters={"department": "HR", "category": "policy", "tenant_id": "company_A"},
    )

    assert answer == "Employees get 20 days of leave."
    assert ids(context) == ["hr_policy", "hr_policy_2"]
    prompt = llm.prompts[0]
    assert "Source: hr_policy.pdf | Page: 1 | Document: doc-hr_policy" in prompt
    assert "Cite the Source and Page" in prompt
    assert "hr_handbook" not in prompt
    assert "b_hr_policy" not in prompt
    assert format_sources(context) == [
        "hr_policy | Source: hr_policy.pdf | Page: 1 | Document: doc-hr_policy",
        "hr_policy_2 | Source: hr_policy_2.pdf | Page: 1 | Document: doc-hr_policy_2",
    ]
