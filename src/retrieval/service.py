from typing import Any

from src.embeddings.service import EmbeddingService
from src.repositories.vector_store_repository import VectorStoreRepository
from src.vector_store.models import SearchResult


class RetrievalService:
    """Find the stored chunks most relevant to a question.

    With expand_context, a matched chunk that carries a larger context
    (parent-child and hierarchical chunking) is returned as that context
    instead; see expand_to_context.
    """

    def __init__(
        self,
        embedding_service: EmbeddingService,
        repository: VectorStoreRepository,
        top_k: int = 5,
        expand_context: bool = False,
    ) -> None:
        self.embedding_service = embedding_service
        self.repository = repository
        self.top_k = top_k
        self.expand_context = expand_context

    def retrieve(
        self,
        question: str,
        top_k: int | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Embed a question and return its most similar chunks.

        filters limits the search to chunks whose metadata matches every
        value, e.g. {"tenant_id": "company_A", "department": "HR"}.
        """
        if not question.strip():
            raise ValueError("Question must not be empty.")

        query_embedding = self.embedding_service.embed_query(question)
        results = self.repository.search(
            query_embedding,
            top_k=self.top_k if top_k is None else top_k,
            filters=filters,
        )
        return expand_to_context(results) if self.expand_context else results


def expand_to_context(results: list[SearchResult]) -> list[SearchResult]:
    """Replace each matched chunk's text with its stored context.

    Several children of one parent collapse into a single result at the
    best child's rank, so the LLM never reads the same parent twice; this
    can return fewer than top_k results. The matched child's own text is
    kept as metadata["matched_text"]. Chunks without context pass through.
    """
    expanded = []
    seen = set()

    for result in results:
        context = result.metadata.get("context_text")
        if not context:
            expanded.append(result)
            continue

        context_id = result.metadata.get("context_id", result.chunk_id)
        if context_id in seen:
            continue
        seen.add(context_id)

        metadata = {
            key: value for key, value in result.metadata.items() if key != "context_text"
        }
        expanded.append(
            SearchResult(
                chunk_id=result.chunk_id,
                text=context,
                metadata={**metadata, "matched_text": result.text},
                score=result.score,
            )
        )

    return expanded
