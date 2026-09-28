import hashlib
import re

from src.embeddings.base import EmbeddingProvider


class HashingEmbeddingProvider(EmbeddingProvider):
    """Bag-of-words vectors from hashed words: free, offline and deterministic.

    Captures word overlap only, not meaning, so it is useful for testing the
    experiment machinery and for a no-cost baseline, not for conclusions
    about semantic chunking.
    """

    def __init__(self, dimension: int = 512) -> None:
        self.dimension = dimension

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        for word in re.findall(r"\w+", text.lower()):
            digest = hashlib.md5(word.encode("utf-8")).digest()
            vector[int.from_bytes(digest[:4], "little") % self.dimension] += 1.0
        # A vector of zeros has no direction to compare.
        vector[0] += 1e-3
        return vector

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(text) for text in texts]
