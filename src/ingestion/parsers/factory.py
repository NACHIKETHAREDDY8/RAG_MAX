from src.ingestion.detection import FileType
from src.ingestion.errors import UnsupportedFileTypeError
from src.ingestion.parsers.base import BaseParser
from src.ingestion.parsers.csv_parser import CsvParser
from src.ingestion.parsers.docx_parser import DocxParser
from src.ingestion.parsers.html_parser import HtmlParser
from src.ingestion.parsers.json_parser import JsonParser
from src.ingestion.parsers.markdown_parser import MarkdownParser
from src.ingestion.parsers.pdf_parser import PdfParser
from src.ingestion.parsers.text_parser import TextParser


class ParserFactory:
    """Choose the parser for a file type."""

    def __init__(self, parsers: list[BaseParser] | None = None) -> None:
        self._parsers: dict[FileType, BaseParser] = {}

        for parser in parsers or []:
            self.register(parser)

    def register(self, parser: BaseParser) -> None:
        """Add a parser, replacing any registered for the same file type."""
        self._parsers[parser.file_type] = parser

    def get_parser(self, file_type: FileType) -> BaseParser:
        try:
            return self._parsers[file_type]
        except KeyError:
            raise UnsupportedFileTypeError(
                f"No parser is registered for {file_type.value} files."
            ) from None

    @property
    def supported_types(self) -> set[FileType]:
        return set(self._parsers)


def default_parser_factory() -> ParserFactory:
    """Return a factory with a parser for every supported format."""
    return ParserFactory(
        [
            PdfParser(),
            DocxParser(),
            TextParser(),
            MarkdownParser(),
            HtmlParser(),
            CsvParser(),
            JsonParser(),
        ]
    )
