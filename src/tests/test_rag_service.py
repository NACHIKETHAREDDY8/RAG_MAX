from src.generation.service import GenerationService
from src.retrieval.service import RetrievalService
from src.services.rag_service import RAGService
from src.tests.conftest import FakeLLM, make_chunk


def test_answer_with_context_retrieves_then_generates(embedding_service, repository):
    chunks = [make_chunk("doc", 0, "cat facts"), make_chunk("doc", 1, "dog facts")]
    repository.add_chunks(chunks, embedding_service.embed_chunks(chunks))
    llm = FakeLLM("Dogs bark.")
    rag_service = RAGService(
        RetrievalService(embedding_service, repository, top_k=1),
        GenerationService(llm),
    )

    answer, context = rag_service.answer_with_context("What about the dog?")

    assert answer == "Dogs bark."
    assert [result.chunk_id for result in context] == ["doc_chunk_1"]
    assert "dog facts" in llm.prompts[0]
    assert rag_service.answer("What about the dog?") == "Dogs bark."
