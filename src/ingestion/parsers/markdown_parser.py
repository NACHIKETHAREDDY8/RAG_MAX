import re
from pathlib import Path

from bs4 import BeautifulSoup
from markdown_it import MarkdownIt

from src.ingestion.detection import FileType
from src.ingestion.models import ParsedDocument, ParsedSection
from src.ingestion.parsers.base import BaseParser, read_text
from src.ingestion.parsers.html_parser import html_to_text

# A "---" fenced block of "key: value" lines at the very top of the file.
FRONT_MATTER = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.DOTALL)
FRONT_MATTER_FIELDS = {"title", "author", "date"}


class MarkdownParser(BaseParser):
    """Markdown rendered to plain text as one section.

    Formatting characters (#, *, backticks, link URLs) are dropped so they do
    not dilute the embeddings; the words, lists and code stay.
    """

    file_type = FileType.MARKDOWN

    def _parse(self, path: Path) -> ParsedDocument:
        markdown, encoding = read_text(path)
        metadata, body = _split_front_matter(markdown)

        renderer = MarkdownIt("commonmark").enable("table")
        soup = BeautifulSoup(renderer.render(body), "html.parser")

        if "title" not in metadata and soup.h1 and soup.h1.get_text(strip=True):
            metadata["title"] = soup.h1.get_text(strip=True)

        return ParsedDocument(
            sections=[ParsedSection(text=html_to_text(soup))],
            metadata={**metadata, "encoding": encoding},
        )


def _split_front_matter(markdown: str) -> tuple[dict, str]:
    """Return the title, author and date from front matter, and the remaining text.

    Only simple "key: value" lines are read, which covers the fields used
    here without needing a YAML parser.
    """
    match = FRONT_MATTER.match(markdown)

    if not match:
        return {}, markdown

    metadata = {}
    for line in match.group(1).splitlines():
        key, separator, value = line.partition(":")
        key = key.strip().lower()
        value = value.strip().strip("\"'")

        if separator and key in FRONT_MATTER_FIELDS and value:
            metadata[key] = value

    if "date" in metadata:
        date = re.match(r"\d{4}-\d{2}-\d{2}", metadata["date"])
        if date:
            metadata["date"] = date.group()
        else:
            del metadata["date"]

    return metadata, markdown[match.end():]
