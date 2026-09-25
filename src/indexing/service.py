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
        if self.is_indexed(document.document_id):
            return 0

        chunks = fixed_size_chunk(
            text=document.text,
            document_id=document.document_id,
            metadata={
                **document.metadata,
                "source": document.filename,
                "page": document.page_number,
            },
            chunk_size=self.chunk_size,
            overlap=self.chunk_overlap,
        )
        self.index_chunks(chunks)
        return len(chunks)

    def is_indexed(self, document_id: str) -> bool:
        return document_id in self.repository.document_ids()

    def count(self) -> int:
        return self.repository.count()

    def save(self) -> None:
        self.repository.save()
