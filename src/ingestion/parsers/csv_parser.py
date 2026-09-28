import csv
from pathlib import Path

from src.ingestion.detection import FileType
from src.ingestion.models import ParsedDocument, ParsedSection
from src.ingestion.parsers.base import BaseParser, read_text

DELIMITERS = ",;\t|"


class CsvParser(BaseParser):
    """A table as one section, one "column: value | ..." line per row.

    The first row is the header. Repeating the column names on every row
    keeps each chunk understandable after fixed-size chunking splits the
    table.
    """

    file_type = FileType.CSV

    def _parse(self, path: Path) -> ParsedDocument:
        text, encoding = read_text(path)
        rows = [
            [cell.strip() for cell in row]
            for row in csv.reader(text.splitlines(), _dialect(text))
        ]
        rows = [row for row in rows if any(row)]

        if not rows:
            return ParsedDocument([ParsedSection(text="")], {"encoding": encoding})

        header, *data = rows
        header = [name or f"column_{number}" for number, name in enumerate(header, 1)]
        lines = [f"Columns: {', '.join(header)}"]

        for row in data:
            names = header + [
                f"column_{number}" for number in range(len(header) + 1, len(row) + 1)
            ]
            lines.append(
                " | ".join(f"{name}: {value}" for name, value in zip(names, row) if value)
            )

        return ParsedDocument(
            sections=[ParsedSection(text="\n".join(lines))],
            metadata={
                "encoding": encoding,
                "row_count": len(data),
                "column_count": len(header),
            },
        )


def _dialect(text: str) -> type[csv.Dialect] | csv.Dialect:
    try:
        return csv.Sniffer().sniff(text[:8192], delimiters=DELIMITERS)
    except csv.Error:
        # One-column files and other ambiguous samples: assume commas.
        return csv.excel
