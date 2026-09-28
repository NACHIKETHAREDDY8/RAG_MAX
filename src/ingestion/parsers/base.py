from abc import ABC, abstractmethod
from pathlib import Path

from src.ingestion.detection import FileType
from src.ingestion.errors import IngestionError, ParserError
from src.ingestion.models import ParsedDocument

# Tried in order after any byte order mark. latin-1 accepts every byte, so
# decoding never fails; cp1252 comes first because Windows tools write it.
FALLBACK_ENCODINGS = ("utf-8", "cp1252", "latin-1")

BOMS = (
    (b"\xef\xbb\xbf", "utf-8-sig"),
    (b"\xff\xfe", "utf-16"),
    (b"\xfe\xff", "utf-16"),
)


class BaseParser(ABC):
    """Extract text and format metadata from one kind of file."""

    file_type: FileType

    def parse(self, path: Path) -> ParsedDocument:
        """Parse a file, reporting any failure as a ParserError."""
        try:
            return self._parse(path)
        except IngestionError:
            raise
        except Exception as error:
            raise ParserError(
                f"Could not read {path.name} as {self.file_type.value}: {error}"
            ) from error

    @abstractmethod
    def _parse(self, path: Path) -> ParsedDocument:
        """Return the file's sections and metadata. May raise anything."""


def read_text(path: Path) -> tuple[str, str]:
    """Return a text file's contents and the encoding they were decoded with."""
    data = path.read_bytes()

    for bom, encoding in BOMS:
        if data.startswith(bom):
            return data.decode(encoding), encoding

    for encoding in FALLBACK_ENCODINGS:
        try:
            return data.decode(encoding), encoding
        except UnicodeDecodeError:
            continue

    raise AssertionError("latin-1 decodes every byte sequence")
