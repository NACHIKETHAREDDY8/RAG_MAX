from pathlib import Path

from src.chunking.models import Chunk
from src.vector_store.base import VectorStore
from src.vector_store.models import SearchResult, VectorRecord


class VectorStoreRepository:
    """Store and query embedded chunks through any VectorStore implementation."""

    def __init__(self, vector_store: VectorStore, path: str | Path) -> None:
        self.vector_store = vector_store
        self.path = Path(path)

    def add_chunks(
        self,
        chunks: list[Chunk],
        embeddings: list[list[float]],
    ) -> None:
        """Store each chunk with its embedding vector."""
        if len(chunks) != len(embeddings):
            raise ValueError("Each chunk needs exactly one embedding.")

        records = [
            VectorRecord(
                chunk_id=chunk.chunk_id,
                text=chunk.text,
                embedding=embedding,
                metadata={**chunk.metadata, "document_id": chunk.document_id},
            )
            for chunk, embedding in zip(chunks, embeddings)
        ]
        self.vector_store.add_many(records)

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> list[SearchResult]:
        """Return the stored chunks most similar to a query vector."""
        return self.vector_store.search(query_embedding, top_k=top_k)

    def document_ids(self) -> set[str]:
        """Return the ids of documents whose chunks are already stored."""
        return {
            record.metadata.get("document_id")
            # Records indexed before document_id was stored only carry it
            # as the chunk id prefix.
            or record.chunk_id.rsplit("_chunk_", 1)[0]
            for record in self.vector_store.list_records()
        }

    def count(self) -> int:
        """Return the number of stored chunks."""
        return self.vector_store.count()

    def save(self) -> None:
        """Persist the stored chunks."""
        self.vector_store.save(self.path)
