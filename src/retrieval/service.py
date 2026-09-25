from src.embeddings.service import EmbeddingService
from src.repositories.vector_store_repository import VectorStoreRepository
from src.vector_store.models import SearchResult


class RetrievalService:
    """Find the stored chunks most relevant to a question."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        repository: VectorStoreRepository,
        top_k: int = 5,
    ) -> None:
        self.embedding_service = embedding_service
        self.repository = repository
        self.top_k = top_k

    def retrieve(self, question: str, top_k: int | None = None) -> list[SearchResult]:
        """Embed a question and return its most similar chunks."""
        if not question.strip():
            raise ValueError("Question must not be empty.")

        query_embedding = self.embedding_service.embed_query(question)
        return self.repository.search(
            query_embedding,
            top_k=self.top_k if top_k is None else top_k,
        )
