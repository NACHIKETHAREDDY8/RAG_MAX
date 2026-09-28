from dataclasses import dataclass, field


@dataclass
class ParsedSection:
    """One piece of a file's raw text: a PDF page, or a whole non-paginated file."""

    text: str
    page_number: int | None = None


@dataclass
class ParsedDocument:
    """What every parser returns, whatever the file format.

    Sections are in file order. Their 1-based position becomes part of each
    Document's id, so a parser must return empty sections (e.g. blank PDF
    pages) rather than dropping them. metadata holds what the format itself
    records, such as author, title or page_count.
    """

    sections: list[ParsedSection]
    metadata: dict = field(default_factory=dict)


@dataclass
class Document:
    document_id: str
    source: str
    filename: str
    # None for formats without pages (DOCX, TXT, Markdown, HTML, CSV, JSON).
    page_number: int | None
    text: str
    metadata: dict = field(default_factory=dict)

    @property
    def label(self) -> str:
        """Name this document in progress messages: 'page 2' or the filename."""
        if self.page_number is None:
            return self.filename
        return f"page {self.page_number}"
