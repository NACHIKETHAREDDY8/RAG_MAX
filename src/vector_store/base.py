from abc import ABC, abstractmethod

from src.vector_store.models import SearchResult, VectorRecord


class VectorStore(ABC):
    """Interface for storing vectors and retrieving similar records."""

    @abstractmethod
    def add(self, record: VectorRecord) -> None:
        """Store one vector record."""

    @abstractmethod
    def add_many(self, records: list[VectorRecord]) -> None:
        """Store multiple vector records."""

    @abstractmethod
    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> list[SearchResult]:
        """Return the records most similar to a query vector."""

    @abstractmethod
    def count(self) -> int:
        """Return the number of stored vector records."""
