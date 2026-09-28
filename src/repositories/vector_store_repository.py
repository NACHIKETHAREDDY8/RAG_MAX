from pathlib import Path
from typing import Any

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
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Return the stored chunks most similar to a query vector."""
        return self.vector_store.search(
            query_embedding,
            top_k=top_k,
            filters=filters,
        )

    def document_ids(self, tenant_id: str | None = None) -> set[str]:
        """Return the ids of documents whose chunks are already stored.

        With a tenant_id, only that tenant's documents are counted, so the
        same file uploaded by two tenants is indexed once for each.
        """
        return {
            self.document_id_of(record)
            for record in self.vector_store.list_records()
            if tenant_id is None or self._belongs_to(record, tenant_id)
        }

    def document_records(self, document_id: str, tenant_id: str) -> list[VectorRecord]:
        """Return a tenant's stored chunks of one document."""
        return [
            record
            for record in self.vector_store.list_records()
            if self.document_id_of(record) == document_id
            and self._belongs_to(record, tenant_id)
        ]

    def file_records(self, filename: str, tenant_id: str) -> list[VectorRecord]:
        """Return a tenant's stored chunks of every version of a file."""
        return [
            record
            for record in self.vector_store.list_records()
            if self.filename_of(record) == filename and self._belongs_to(record, tenant_id)
        ]

    def update_metadata(self, chunk_id: str, metadata: dict[str, Any]) -> None:
        """Replace a stored chunk's metadata without re-embedding it."""
        self.vector_store.update_metadata(chunk_id, metadata)

    def delete_chunks(self, chunk_ids: list[str]) -> int:
        """Remove stored chunks and return how many were removed."""
        return self.vector_store.delete(chunk_ids)

    @staticmethod
    def filename_of(record: VectorRecord) -> str | None:
        # Records indexed before Phase 9 stored the filename as "source".
        return record.metadata.get("filename", record.metadata.get("source"))

    @staticmethod
    def document_id_of(record: VectorRecord) -> str:
        # Records indexed before document_id was stored only carry it as the
        # chunk id prefix.
        return (
            record.metadata.get("document_id")
            or record.chunk_id.rsplit("_chunk_", 1)[0]
        )

    @staticmethod
    def _belongs_to(record: VectorRecord, tenant_id: str) -> bool:
        # Records indexed before tenants existed have no owner yet. They count
        # as indexed for any tenant, so the first tenant to index the document
        # adopts them through a metadata refresh instead of re-embedding.
        return record.metadata.get("tenant_id", tenant_id) == tenant_id

    def count(self) -> int:
        """Return the number of stored chunks."""
        return self.vector_store.count()

    def save(self) -> None:
        """Persist the stored chunks."""
        self.vector_store.save(self.path)
