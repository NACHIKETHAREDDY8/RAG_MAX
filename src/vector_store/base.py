from abc import ABC, abstractmethod
from collections.abc import Collection
from pathlib import Path
from typing import Any

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
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Return the records most similar to a query vector.

        When filters are given, only records whose metadata equals every
        filter value are searched, so top_k is filled from matches alone.
        """

    @abstractmethod
    def update_metadata(self, chunk_id: str, metadata: dict[str, Any]) -> None:
        """Replace one stored record's metadata, keeping its text and vector."""

    @abstractmethod
    def delete(self, chunk_ids: Collection[str]) -> int:
        """Remove the records with these chunk ids and return how many were removed."""

    @abstractmethod
    def count(self) -> int:
        """Return the number of stored vector records."""

    @abstractmethod
    def list_records(self) -> list[VectorRecord]:
        """Return every stored vector record."""

    @abstractmethod
    def save(self, path: str | Path) -> None:
        """Persist the stored records to a location."""
