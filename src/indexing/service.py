import config
from logger import get_logger
from src.chunking.base import Chunker
from src.chunking.fixed import FixedSizeChunker
from src.chunking.models import CHUNK_METADATA_KEYS, Chunk
from src.embeddings.service import EmbeddingService
from src.indexing.versioning import DocumentVersioning, VersionInfo
from src.ingestion.models import Document
from src.repositories.vector_store_repository import VectorStoreRepository

logger = get_logger(__name__)


class IndexingService:
    """Chunk documents, embed the chunks, and store them.

    chunker is any Chunker strategy; without one, documents are cut into
    fixed chunk_size-character chunks as before Phase 11.
    """

    def __init__(
        self,
        embedding_service: EmbeddingService,
        repository: VectorStoreRepository,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        chunker: Chunker | None = None,
    ) -> None:
        self.embedding_service = embedding_service
        self.repository = repository
        self.chunker = chunker or FixedSizeChunker(chunk_size, chunk_overlap)
        self.versioning = DocumentVersioning(repository)

    def index_chunks(self, chunks: list[Chunk]) -> None:
        """Embed chunks and store their vectors with the chunk content."""
        embeddings = self.embedding_service.embed_chunks(chunks)
        self.repository.add_chunks(chunks, embeddings)

    def index_document(self, document: Document) -> int:
        """Index a document's chunks and return how many were added.

        Returns 0 when the document is already indexed. When it is a new
        version of a file the tenant indexed before, the older version's
        chunks are removed once the new ones are stored.
        """
        return sum(chunk.retrievable for chunk in self.chunk_and_index(document))

    def chunk_and_index(self, document: Document) -> list[Chunk]:
        """Index a document and return every chunk the chunker produced.

        Context-only chunks (parents, sections) are returned but not
        embedded; their text reaches the store as their children's context.
        Returns [] when the document is already indexed.
        """
        tenant_id = self._tenant_id(document)

        if self.is_indexed(document.document_id, tenant_id):
            return []

        version = self.versioning.resolve(document, tenant_id)

        chunks = self.chunker.chunk(
            document.text,
            document.document_id,
            self._chunk_metadata(document, tenant_id, version),
            # document_id is a content hash, so the same file indexed for two
            # tenants needs the tenant in its chunk ids to keep them unique.
            chunk_id_prefix=f"{tenant_id}:{document.document_id}",
        )
        retrievable = [chunk for chunk in chunks if chunk.retrievable]

        if not retrievable:
            return []

        self.index_chunks(retrievable)

        retired = self.versioning.retire_older_versions(document, tenant_id)
        if retired:
            logger.info(
                "Removed %d chunks of older versions of %s (now version %d)",
                retired,
                document.filename,
                version.version,
            )

        return chunks

    def refresh_metadata(self, document: Document) -> int:
        """Update an indexed document's stored metadata without re-embedding.

        Picks up .meta.json edits and upgrades chunks indexed before metadata
        filtering existed. Only chunks stored from this file are touched: an
        identical file under another name keeps its own metadata. Returns how
        many chunks changed.
        """
        tenant_id = self._tenant_id(document)
        metadata = self._chunk_metadata(
            document, tenant_id, self.versioning.resolve(document, tenant_id)
        )
        changed = 0

        for record in self.repository.document_records(document.document_id, tenant_id):
            # What the chunker recorded (offsets, parent, section) is not
            # document metadata and stays as it was.
            updated = {
                **metadata,
                **{
                    key: value
                    for key, value in record.metadata.items()
                    if key in CHUNK_METADATA_KEYS
                },
            }
            if (
                self.repository.filename_of(record) != document.filename
                or record.metadata == updated
            ):
                continue

            self.repository.update_metadata(record.chunk_id, updated)
            changed += 1

        return changed

    def duplicate_of(self, document: Document) -> str | None:
        """Return the name of an identical file this tenant already indexed.

        Returns None when the document is stored under its own name or not
        stored at all.
        """
        tenant_id = self._tenant_id(document)
        filenames = {
            self.repository.filename_of(record)
            for record in self.repository.document_records(document.document_id, tenant_id)
        }

        if document.filename in filenames:
            return None
        return min((name for name in filenames if name), default=None)

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
    def _chunk_metadata(
        document: Document,
        tenant_id: str,
        version: VersionInfo,
    ) -> dict:
        metadata = {
            **document.metadata,
            **version.as_metadata(),
            "tenant_id": tenant_id,
            "document_id": document.document_id,
            "filename": document.filename,
        }

        # Formats without pages get no page, so sources never cite a
        # page that does not exist.
        if document.page_number is not None:
            metadata["page"] = document.page_number

        return metadata
