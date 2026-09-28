"""Turn any supported file into cleaned Documents ready for indexing."""

from dataclasses import dataclass
from pathlib import Path

from src.ingestion.cleaner import clean_text
from src.ingestion.detection import FileType, detect_file_type
from src.ingestion.hashing import make_document_id, sha256_file
from src.ingestion.metadata import build_metadata, is_sidecar
from src.ingestion.models import Document
from src.ingestion.parsers.factory import ParserFactory, default_parser_factory
from src.ingestion.validation import validate_file

DEFAULT_MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024


@dataclass
class IngestionResult:
    path: Path
    file_type: FileType
    file_hash: str
    metadata: dict
    # Empty when the file has no extractable text, e.g. a scanned PDF.
    documents: list[Document]


class IngestionPipeline:
    """validate → detect type → choose parser → parse → clean → metadata → hash."""

    def __init__(
        self,
        parser_factory: ParserFactory | None = None,
        max_file_size_bytes: int = DEFAULT_MAX_FILE_SIZE_BYTES,
    ) -> None:
        self.parser_factory = parser_factory or default_parser_factory()
        self.max_file_size_bytes = max_file_size_bytes

    def ingest(self, file_path: str | Path, mime_type: str | None = None) -> IngestionResult:
        """Return one Document per non-empty section of a file.

        Raises an IngestionError subclass when the file cannot be ingested.
        """
        path = validate_file(file_path, self.max_file_size_bytes)
        detected = detect_file_type(path, mime_type)
        parsed = self.parser_factory.get_parser(detected.file_type).parse(path)
        file_hash = sha256_file(path)
        metadata = build_metadata(path, detected, parsed.metadata, file_hash)
        documents = []

        for section_number, section in enumerate(parsed.sections, start=1):
            text = clean_text(section.text)

            if not text:
                continue

            documents.append(
                Document(
                    document_id=make_document_id(file_hash, section_number),
                    source=str(path),
                    filename=path.name,
                    page_number=section.page_number,
                    text=text,
                    metadata=metadata.copy(),
                )
            )

        return IngestionResult(
            path=path,
            file_type=detected.file_type,
            file_hash=file_hash,
            metadata=metadata,
            documents=documents,
        )


def find_documents(directory: Path) -> list[Path]:
    """Return every candidate document in a folder, sorted by name.

    Unsupported files are included so the caller can report them; .meta.json
    sidecars and hidden files are not documents and are left out.
    """
    return sorted(
        path
        for path in directory.iterdir()
        if path.is_file() and not path.name.startswith(".") and not is_sidecar(path)
    )
