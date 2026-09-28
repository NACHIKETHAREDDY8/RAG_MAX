"""Track versions of a file whose content changes under the same name."""

from dataclasses import dataclass

from src.ingestion.hashing import file_key
from src.ingestion.models import Document
from src.repositories.vector_store_repository import VectorStoreRepository


@dataclass(frozen=True)
class VersionInfo:
    version: int
    # file_key (content hash prefix) of the version this one replaced.
    previous_version: str | None = None

    def as_metadata(self) -> dict:
        metadata = {"version": self.version}
        if self.previous_version:
            metadata["previous_version"] = self.previous_version
        return metadata


class DocumentVersioning:
    """Number the versions of each (tenant, filename) and retire old ones.

    A version is one distinct content hash stored under a filename. Only the
    latest version stays searchable, so an edited file never returns stale
    chunks alongside current ones.
    """

    def __init__(self, repository: VectorStoreRepository) -> None:
        self.repository = repository

    def resolve(self, document: Document, tenant_id: str) -> VersionInfo:
        """Return the version a document's file is, or would be once stored."""
        stored = self._stored_versions(document.filename, tenant_id)
        current = file_key(document.document_id)

        if current in stored:
            return stored[current]

        if not stored:
            return VersionInfo(version=1)

        latest_key, latest = max(stored.items(), key=lambda item: item[1].version)
        return VersionInfo(version=latest.version + 1, previous_version=latest_key)

    def retire_older_versions(self, document: Document, tenant_id: str) -> int:
        """Delete the tenant's chunks of this filename from other versions.

        Returns how many chunks were removed.
        """
        current = file_key(document.document_id)
        stale = [
            record.chunk_id
            for record in self.repository.file_records(document.filename, tenant_id)
            if file_key(self.repository.document_id_of(record)) != current
        ]

        return self.repository.delete_chunks(stale) if stale else 0

    def _stored_versions(self, filename: str, tenant_id: str) -> dict[str, VersionInfo]:
        versions = {}

        for record in self.repository.file_records(filename, tenant_id):
            key = file_key(self.repository.document_id_of(record))
            # Chunks stored before versioning existed count as version 1.
            versions[key] = VersionInfo(
                version=record.metadata.get("version", 1),
                previous_version=record.metadata.get("previous_version"),
            )

        return versions
