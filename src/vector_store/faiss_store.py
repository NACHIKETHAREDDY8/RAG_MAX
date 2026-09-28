import faiss
import numpy as np
from pathlib import Path
import json
from collections.abc import Collection
from typing import Any

import config
from src.vector_store.base import VectorStore
from src.vector_store.filters import matches_filters, validate_filters
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
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        if top_k <= 0:
            raise ValueError("top_k must be greater than 0")

        validate_filters(filters)

        query = np.asarray([query_embedding], dtype=np.float32)
        self._validate_vectors(query)

        if not self.records:
            raise ValueError("Cannot search an empty vector index.")

        faiss.normalize_L2(query)

        if filters:
            # Filter before ranking: FAISS scores only the matching records,
            # so a filtered search still returns up to top_k results.
            candidate_ids = [
                position
                for position, record in enumerate(self.records)
                if matches_filters(record.metadata, filters)
            ]

            if not candidate_ids:
                return []

            selector = faiss.IDSelectorBatch(candidate_ids)
            scores, indices = self.index.search(
                query,
                min(top_k, len(candidate_ids)),
                params=faiss.SearchParameters(sel=selector),
            )
        else:
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

    def update_metadata(self, chunk_id: str, metadata: dict[str, Any]) -> None:
        matches = [record for record in self.records if record.chunk_id == chunk_id]

        if len(matches) != 1:
            raise KeyError(
                f"Expected one record with chunk id {chunk_id!r}, "
                f"found {len(matches)}."
            )

        matches[0].metadata = dict(metadata)

    def delete(self, chunk_ids: Collection[str]) -> int:
        targets = set(chunk_ids)
        positions = {
            position
            for position, record in enumerate(self.records)
            if record.chunk_id in targets
        }

        if not positions:
            return 0

        # A flat index closes the gaps in order, so FAISS positions keep
        # matching self.records once the same positions are dropped there.
        self.index.remove_ids(faiss.IDSelectorBatch(sorted(positions)))
        self.records = [
            record
            for position, record in enumerate(self.records)
            if position not in positions
        ]
        return len(positions)

    def list_records(self) -> list[VectorRecord]:
        return list(self.records)

    def save(self, path: str | Path) -> None:
        """Persist the FAISS index and its chunk records."""
        index_path = Path(path)
        records_path = self._records_path(index_path)

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
        records_path = cls._records_path(index_path)

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

    @classmethod
    def load_or_create(
        cls,
        path: str | Path,
        dimension: int = config.EMBEDDING_DIMENSION,
    ) -> "FAISSVectorStore":
        """Restore a saved index when both of its files exist, otherwise start empty."""
        index_path = Path(path)

        if index_path.exists() and cls._records_path(index_path).exists():
            return cls.load(index_path)

        return cls(dimension=dimension)

    def count(self) -> int:
        return len(self.records)

    @staticmethod
    def _records_path(index_path: Path) -> Path:
        return index_path.with_suffix(index_path.suffix + ".json")

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
