import hashlib
from pathlib import Path

import numpy as np

from src.embeddings.base import EmbeddingProvider


class CachedEmbeddingProvider(EmbeddingProvider):
    """Remember embeddings by text, so the same text is only paid for once.

    namespace should name the model: a vector from one model is meaningless
    to another. With a path, the cache is saved as a .npz file after every
    batch that added something, and loaded on construction.
    """

    def __init__(
        self,
        provider: EmbeddingProvider,
        namespace: str,
        path: str | Path | None = None,
    ) -> None:
        self.provider = provider
        self.namespace = namespace
        self.path = Path(path) if path else None
        self.vectors: dict[str, list[float]] = {}
        self.hits = 0
        self.misses = 0

        if self.path and self.path.exists():
            with np.load(self.path) as data:
                self.vectors = dict(zip(data["keys"].tolist(), data["vectors"].tolist()))

    def embed(self, text: str) -> list[float]:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        keys = [self._key(text) for text in texts]
        missing = {key: text for key, text in zip(keys, texts) if key not in self.vectors}
        self.misses += len(missing)
        self.hits += len(texts) - len(missing)

        if missing:
            embeddings = self.provider.embed_batch(list(missing.values()))
            self.vectors.update(zip(missing, embeddings))
            self._save()

        return [self.vectors[key] for key in keys]

    def _key(self, text: str) -> str:
        return hashlib.sha256(f"{self.namespace}\0{text}".encode("utf-8")).hexdigest()

    def _save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(
            self.path,
            keys=np.asarray(list(self.vectors)),
            vectors=np.asarray(list(self.vectors.values()), dtype=np.float32),
        )
