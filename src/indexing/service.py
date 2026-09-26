import config
from src.chunking.fixed import fixed_size_chunk
from src.chunking.models import Chunk
from src.embeddings.service import EmbeddingService
from src.ingestion.models import Document
from src.repositories.vector_store_repository import VectorStoreRepository


class IndexingService:
    """Chunk documents, embed the chunks, and store them."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        repository: VectorStoreRepository,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ) -> None:
        self.embedding_service = embedding_service
        self.repository = repository
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def index_chunks(self, chunks: list[Chunk]) -> None:
        """Embed chunks and store their vectors with the chunk content."""
        embeddings = self.embedding_service.embed_chunks(chunks)
        self.repository.add_chunks(chunks, embeddings)

    def index_document(self, document: Document) -> int:
        """Index a document's chunks and return how many were added.

        Returns 0 when the document is already indexed.
        """
        tenant_id = self._tenant_id(document)

        if self.is_indexed(document.document_id, tenant_id):
            return 0

        chunks = fixed_size_chunk(
            text=document.text,
            document_id=document.document_id,
            # document_id is a content hash, so the same file indexed for two
            # tenants needs the tenant in its chunk ids to keep them unique.
            chunk_id_prefix=f"{tenant_id}:{document.document_id}",
            metadata=self._chunk_metadata(document, tenant_id),
            chunk_size=self.chunk_size,
            overlap=self.chunk_overlap,
        )
        self.index_chunks(chunks)
        return len(chunks)

    def refresh_metadata(self, document: Document) -> int:
        """Update an indexed document's stored metadata without re-embedding.

        Picks up .meta.json edits and upgrades chunks indexed before metadata
        filtering existed. Only chunks stored from this file are touched: an
        identical file under another name keeps its own metadata. Returns how
        many chunks changed.
        """
        tenant_id = self._tenant_id(document)
        metadata = self._chunk_metadata(document, tenant_id)
        changed = 0

        for record in self.repository.document_records(document.document_id, tenant_id):
            # Records indexed before Phase 9 stored the filename as "source".
            stored_filename = record.metadata.get(
                "filename", record.metadata.get("source")
            )

            if stored_filename != document.filename or record.metadata == metadata:
                continue

            self.repository.update_metadata(record.chunk_id, metadata)
            changed += 1

        return changed

    def is_indexed(self, document_id: str, tenant_id: str | None = None) -> bool:
        return document_id in self.repository.document_ids(tenant_id)

    def count(self) -> int:
        return self.repository.count()

    def save(self) -> None:
        self.repository.save()

    @staticmethod
    def _tenant_id(document: Document) -> str:
        # Every stored chunk belongs to exactly one tenant, so tenant-filtered
        # searches never see chunks with no owner.
        return document.metadata.get("tenant_id", config.DEFAULT_TENANT_ID)

    @staticmethod
    def _chunk_metadata(document: Document, tenant_id: str) -> dict:
        return {
            **document.metadata,
            "tenant_id": tenant_id,
            "document_id": document.document_id,
            "filename": document.filename,
            "page": document.page_number,
        }
