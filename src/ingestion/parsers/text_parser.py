from pathlib import Path

from src.ingestion.detection import FileType
from src.ingestion.models import ParsedDocument, ParsedSection
from src.ingestion.parsers.base import BaseParser, read_text


class TextParser(BaseParser):
    """A plain text file as one section."""

    file_type = FileType.TXT

    def _parse(self, path: Path) -> ParsedDocument:
        text, encoding = read_text(path)

        return ParsedDocument(
            sections=[ParsedSection(text=text)],
            metadata={"encoding": encoding},
        )
