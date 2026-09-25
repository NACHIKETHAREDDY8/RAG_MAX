import faiss
import numpy as np
from pathlib import Path
import json

import config
from src.vector_store.base import VectorStore
from src.vector_store.models import SearchResult, VectorRecord


class FAISSVectorStore(VectorStore):
    """In-memory FAISS store using cosine similarity."""

    def __init__(self, dimension: int = config.EMBEDDING_DIMENSION) -> None:
        if dimension <= 0:
            raise ValueError("dimension must be greater than 0")

        self.dimension = dimension
        self.index = faiss.IndexFlatIP(dimension)
        self.records: list[VectorRecord] = []

    def add(self, record: VectorRecord) -> None:
        self.add_many([record])

    def add_many(self, records: list[VectorRecord]) -> None:
        if not records:
            return

        vectors = np.asarray(
            [record.embedding for record in records],
            dtype=np.float32,
        )
        self._validate_vectors(vectors)
        faiss.normalize_L2(vectors)
        self.index.add(vectors)
        self.records.extend(records)

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> list[SearchResult]:
        if top_k <= 0:
            raise ValueError("top_k must be greater than 0")

        query = np.asarray([query_embedding], dtype=np.float32)
        self._validate_vectors(query)

        if not self.records:
            raise ValueError("Cannot search an empty vector index.")

        faiss.normalize_L2(query)

        result_count = min(top_k, len(self.records))
        scores, indices = self.index.search(query, result_count)

        return [
            SearchResult(
                chunk_id=self.records[index].chunk_id,
                text=self.records[index].text,
                metadata=self.records[index].metadata,
                score=float(score),
            )
            for score, index in zip(scores[0], indices[0])
            if index >= 0
        ]

    def save(self, path: str | Path) -> None:
        """Persist the FAISS index and its chunk records."""
        index_path = Path(path)
        records_path = index_path.with_suffix(index_path.suffix + ".json")

        faiss.write_index(self.index, str(index_path))
        records_path.write_text(
            json.dumps(
                {
                    "dimension": self.dimension,
                    "records": [record.__dict__ for record in self.records],
                }
            ),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: str | Path) -> "FAISSVectorStore":
        """Restore a FAISS index and its chunk records."""
        index_path = Path(path)
        records_path = index_path.with_suffix(index_path.suffix + ".json")

        index = faiss.read_index(str(index_path))
        payload = json.loads(records_path.read_text(encoding="utf-8"))
        store = cls(dimension=payload["dimension"])
        store.index = index
        store.records = [
            VectorRecord(
                chunk_id=record["chunk_id"],
                text=record["text"],
                embedding=record["embedding"],
                metadata=record["metadata"],
            )
            for record in payload["records"]
        ]

        if store.index.ntotal != len(store.records):
            raise ValueError("FAISS index and stored records are out of sync.")

        return store

    def count(self) -> int:
        return len(self.records)

    def _validate_vectors(self, vectors: np.ndarray) -> None:
        if vectors.ndim != 2 or vectors.shape[1] != self.dimension:
            actual_dimension = vectors.shape[1] if vectors.ndim == 2 else 0
            raise ValueError(
                f"Vector dimension must be {self.dimension}, "
                f"got {actual_dimension}."
            )

        if not np.isfinite(vectors).all():
            raise ValueError("Vectors must contain only finite values.")

        if np.any(np.linalg.norm(vectors, axis=1) == 0):
            raise ValueError("Zero vectors cannot be indexed or searched.")
