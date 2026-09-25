from src.generation.service import GenerationService
from src.retrieval.service import RetrievalService
from src.vector_store.models import SearchResult


class RAGService:
    """Answer questions by retrieving context and generating from it."""

    def __init__(
        self,
        retrieval_service: RetrievalService,
        generation_service: GenerationService,
    ) -> None:
        self.retrieval_service = retrieval_service
        self.generation_service = generation_service

    def answer(self, question: str, top_k: int | None = None) -> str:
        """Return a grounded answer to a question."""
        answer, _ = self.answer_with_context(question, top_k=top_k)
        return answer

    def answer_with_context(
        self,
        question: str,
        top_k: int | None = None,
    ) -> tuple[str, list[SearchResult]]:
        """Return a grounded answer and the retrieved context it used."""
        context = self.retrieval_service.retrieve(question, top_k=top_k)
        return self.generation_service.generate(question, context), context
