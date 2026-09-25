import config
from src.chunking.models import Chunk
from src.embeddings.base import EmbeddingProvider


def cosine_similarity(vector_a: list[float], vector_b: list[float]) -> float:
    """Return the cosine similarity between two vectors."""
    if len(vector_a) != len(vector_b):
        raise ValueError("Vectors must have the same dimension.")

    magnitude_a = sum(value * value for value in vector_a) ** 0.5
    magnitude_b = sum(value * value for value in vector_b) ** 0.5

    if magnitude_a == 0 or magnitude_b == 0:
        raise ValueError("Cosine similarity is undefined for zero vectors.")

    dot_product = sum(
        value_a * value_b for value_a, value_b in zip(vector_a, vector_b)
    )

    return dot_product / (magnitude_a * magnitude_b)

class EmbeddingService:
    """Coordinate embedding requests through an injected provider."""

    def __init__(self, provider: EmbeddingProvider) -> None:
        self.provider = provider

    def embed_text(self, text: str) -> list[float]:
        """Generate one embedding vector for a text value."""
        embedding = self.provider.embed(text)
        self._validate_embedding(embedding)
        return embedding

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embedding vectors for a batch of text values."""
        embeddings = self.provider.embed_batch(texts)

        if len(embeddings) != len(texts):
            raise ValueError(
                "Embedding provider returned a different number of vectors "
                "than input texts."
            )

        for embedding in embeddings:
            self._validate_embedding(embedding)

        return embeddings

    def embed_chunk(self, chunk: Chunk) -> list[float]:
        """Generate one embedding vector for a chunk."""
        return self.embed_text(chunk.text)

    def embed_chunks(self, chunks: list[Chunk]) -> list[list[float]]:
        """Generate embedding vectors for a batch of chunks."""
        return self.embed_texts([chunk.text for chunk in chunks])

    def embed_query(self, query: str) -> list[float]:
        """Generate one embedding vector for a search query."""
        return self.embed_text(query)

    @staticmethod
    def _validate_embedding(embedding: list[float]) -> None:
        if len(embedding) != config.EMBEDDING_DIMENSION:
            raise ValueError(
                f"Embedding vector must contain {config.EMBEDDING_DIMENSION} "
                f"values, got {len(embedding)}."
            )
