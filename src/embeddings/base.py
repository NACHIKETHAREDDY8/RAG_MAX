from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    """Interface for services that convert text into embedding vectors."""

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Return an embedding vector for one piece of text."""

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Return embedding vectors in the same order as the input texts."""
