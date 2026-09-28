from pathlib import Path

from pypdf import PdfReader

from src.ingestion.detection import FileType
from src.ingestion.models import ParsedDocument, ParsedSection
from src.ingestion.parsers.base import BaseParser


class PdfParser(BaseParser):
    """One section per page, numbered from 1, including blank pages."""

    file_type = FileType.PDF

    def _parse(self, path: Path) -> ParsedDocument:
        reader = PdfReader(path)

        if reader.is_encrypted:
            # Many "protected" PDFs only restrict printing and open with an
            # empty password; others fail here and are reported as such.
            reader.decrypt("")

        sections = [
            ParsedSection(text=page.extract_text() or "", page_number=page_number)
            for page_number, page in enumerate(reader.pages, start=1)
        ]

        return ParsedDocument(
            sections=sections,
            metadata={**pdf_metadata(reader), "page_count": len(sections)},
        )


def pdf_metadata(reader: PdfReader) -> dict:
    """Return the author and creation date embedded in a PDF, when present."""
    info = reader.metadata
    metadata = {}

    if info is None:
        return metadata

    if info.author and info.author.strip():
        metadata["author"] = info.author.strip()

    try:
        created = info.creation_date
    except ValueError:
        # Some PDF writers store dates pypdf cannot parse; the date is optional.
        created = None

    if created:
        metadata["date"] = created.date().isoformat()

    return metadata
