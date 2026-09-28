"""Decide what kind of document a file is."""

import mimetypes
import zipfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from src.ingestion.errors import FileValidationError, UnsupportedFileTypeError


class FileType(str, Enum):
    """Supported formats. The value is stored as the source_type metadata."""

    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    MARKDOWN = "markdown"
    HTML = "html"
    CSV = "csv"
    JSON = "json"


EXTENSION_TYPES = {
    ".pdf": FileType.PDF,
    ".docx": FileType.DOCX,
    ".txt": FileType.TXT,
    ".text": FileType.TXT,
    ".md": FileType.MARKDOWN,
    ".markdown": FileType.MARKDOWN,
    ".html": FileType.HTML,
    ".htm": FileType.HTML,
    ".csv": FileType.CSV,
    ".json": FileType.JSON,
}

# The MIME type recorded for each format, whatever the OS registry says:
# Windows, for example, often knows no type for .md.
CANONICAL_MIME_TYPES = {
    FileType.PDF: "application/pdf",
    FileType.DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    FileType.TXT: "text/plain",
    FileType.MARKDOWN: "text/markdown",
    FileType.HTML: "text/html",
    FileType.CSV: "text/csv",
    FileType.JSON: "application/json",
}

MIME_TYPES = {
    **{mime: file_type for file_type, mime in CANONICAL_MIME_TYPES.items()},
    "text/x-markdown": FileType.MARKDOWN,
    "application/xhtml+xml": FileType.HTML,
    "application/csv": FileType.CSV,
    "text/json": FileType.JSON,
}

TEXT_TYPES = {FileType.TXT, FileType.MARKDOWN, FileType.HTML, FileType.CSV, FileType.JSON}

# How much of a file is read to check its content matches its type.
SNIFF_BYTES = 8192


@dataclass(frozen=True)
class DetectedType:
    file_type: FileType
    mime_type: str


def supported_extensions() -> list[str]:
    return sorted(EXTENSION_TYPES)


def detect_file_type(path: Path, mime_type: str | None = None) -> DetectedType:
    """Return a file's type from its extension, or else its MIME type.

    mime_type is the type a caller was told, such as an upload's
    Content-Type; without it, one is guessed from the filename. The file's
    first bytes must then look like that type.
    """
    file_type = EXTENSION_TYPES.get(path.suffix.lower())

    if file_type is None:
        guessed = mime_type or mimetypes.guess_type(path.name)[0]
        if guessed:
            file_type = MIME_TYPES.get(guessed.split(";")[0].strip().lower())

    if file_type is None:
        raise UnsupportedFileTypeError(
            f"Unsupported file type {path.suffix or '(no extension)'!r} for "
            f"{path.name}. Supported extensions: {', '.join(supported_extensions())}."
        )

    _check_signature(path, file_type)
    return DetectedType(file_type, CANONICAL_MIME_TYPES[file_type])


def _check_signature(path: Path, file_type: FileType) -> None:
    with path.open("rb") as file:
        head = file.read(SNIFF_BYTES)

    if file_type is FileType.PDF:
        # The PDF spec allows the header anywhere in the first 1024 bytes.
        if b"%PDF-" not in head[:1024]:
            raise FileValidationError(f"{path.name} is not a valid PDF file.")

    elif file_type is FileType.DOCX:
        if not zipfile.is_zipfile(path):
            raise FileValidationError(f"{path.name} is not a valid DOCX file.")
        with zipfile.ZipFile(path) as archive:
            if "word/document.xml" not in archive.namelist():
                raise FileValidationError(f"{path.name} is not a valid DOCX file.")

    elif file_type in TEXT_TYPES and _looks_binary(head):
        raise FileValidationError(
            f"{path.name} looks like a binary file, not {file_type.value} text."
        )


def _looks_binary(head: bytes) -> bool:
    # UTF-16 text is full of NUL bytes but starts with a byte order mark.
    if head.startswith((b"\xff\xfe", b"\xfe\xff")):
        return False
    return b"\x00" in head
