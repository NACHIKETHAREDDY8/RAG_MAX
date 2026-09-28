from pathlib import Path

import docx
from docx.table import Table

from src.ingestion.detection import FileType
from src.ingestion.models import ParsedDocument, ParsedSection
from src.ingestion.parsers.base import BaseParser


class DocxParser(BaseParser):
    """Body paragraphs and tables, in document order, as one section."""

    file_type = FileType.DOCX

    def _parse(self, path: Path) -> ParsedDocument:
        document = docx.Document(str(path))
        blocks = []

        for block in document.iter_inner_content():
            if isinstance(block, Table):
                blocks.extend(_table_rows(block))
            elif block.text.strip():
                blocks.append(block.text)

        return ParsedDocument(
            sections=[ParsedSection(text="\n".join(blocks))],
            metadata=_core_metadata(document),
        )


def _table_rows(table: Table) -> list[str]:
    rows = []

    for row in table.rows:
        cells = []
        for cell in row.cells:
            text = cell.text.strip()
            # A merged cell is returned once per grid column it spans.
            if text and (not cells or cells[-1] != text):
                cells.append(text)
        if cells:
            rows.append(" | ".join(cells))

    return rows


def _core_metadata(document) -> dict:
    properties = document.core_properties
    metadata = {}

    if properties.author and properties.author.strip():
        metadata["author"] = properties.author.strip()
    if properties.title and properties.title.strip():
        metadata["title"] = properties.title.strip()
    if properties.created:
        metadata["date"] = properties.created.date().isoformat()

    return metadata
