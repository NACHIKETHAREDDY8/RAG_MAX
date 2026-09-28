import re
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString

from src.ingestion.detection import FileType
from src.ingestion.models import ParsedDocument, ParsedSection
from src.ingestion.parsers.base import BaseParser, read_text

# Elements whose content is never visible text.
HIDDEN_TAGS = ["script", "style", "noscript", "template", "svg", "head"]

# Elements that start a new line when rendered. Without the line breaks,
# get_text() runs "<p>One</p><p>Two</p>" together as "OneTwo".
BLOCK_TAGS = [
    "address", "article", "aside", "blockquote", "dd", "div", "dl", "dt",
    "figcaption", "figure", "footer", "form", "h1", "h2", "h3", "h4", "h5",
    "h6", "header", "hr", "li", "main", "nav", "ol", "p", "pre", "section",
    "table", "tr", "ul",
]

HEADING_TAGS = ["h1", "h2", "h3", "h4", "h5", "h6"]

DATE_META_NAMES = {"date", "dc.date", "dcterms.created", "article:published_time"}


class HtmlParser(BaseParser):
    """The visible text of a page as one section, with its title and author."""

    file_type = FileType.HTML

    def _parse(self, path: Path) -> ParsedDocument:
        html, encoding = read_text(path)
        soup = BeautifulSoup(html, "html.parser")
        metadata = {**_head_metadata(soup), "encoding": encoding}

        return ParsedDocument(
            sections=[ParsedSection(text=html_to_text(soup))],
            metadata=metadata,
        )


def html_to_text(soup: BeautifulSoup) -> str:
    """Return the visible text of parsed HTML, one block element per line.

    Modifies soup.
    """
    for tag in soup.find_all(HIDDEN_TAGS):
        tag.decompose()

    for tag in soup.find_all("br"):
        tag.replace_with("\n")
    # Source line breaks between cells (as markdown-it writes tables) would
    # otherwise put every cell on its own line and lose the rows.
    for row in soup.find_all("tr"):
        for child in list(row.children):
            if isinstance(child, NavigableString) and not child.strip():
                child.extract()
    # Headings, list items and code keep a Markdown marker so chunkers can
    # still see the document's structure once the tags are gone.
    for tag in soup.find_all(HEADING_TAGS):
        tag.insert(0, "#" * int(tag.name[1]) + " ")
    for tag in soup.find_all("li"):
        # In a loose list the text sits in a <p>, which starts its own line;
        # the marker goes inside it so it stays on the item's line.
        first = next(
            (child for child in tag.children if not isinstance(child, NavigableString) or child.strip()),
            None,
        )
        target = first if first is not None and first.name in BLOCK_TAGS else tag
        target.insert(0, "- ")
    for tag in soup.find_all("pre"):
        tag.insert(0, "```\n")
        tag.append("\n```")
    for tag in soup.find_all(["td", "th"]):
        tag.insert_after(" | ")
    for tag in soup.find_all(BLOCK_TAGS):
        tag.insert_before("\n")
        tag.insert_after("\n")

    lines = (
        re.sub(r"[ \t]+", " ", line).strip().rstrip("|").strip()
        for line in soup.get_text().splitlines()
    )

    # Source whitespace between tags varies, so blank lines carry no meaning.
    return "\n".join(line for line in lines if line)


def _head_metadata(soup: BeautifulSoup) -> dict:
    metadata = {}

    if soup.title and soup.title.string and soup.title.string.strip():
        metadata["title"] = soup.title.string.strip()

    for meta in soup.find_all("meta"):
        name = (meta.get("name") or meta.get("property") or "").strip().lower()
        content = (meta.get("content") or "").strip()

        if not content:
            continue
        if name == "author":
            metadata["author"] = content
        elif name in DATE_META_NAMES and re.match(r"\d{4}-\d{2}-\d{2}", content):
            metadata.setdefault("date", content[:10])

    return metadata
