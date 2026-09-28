import json
from pathlib import Path
from typing import Any

from src.ingestion.detection import FileType
from src.ingestion.models import ParsedDocument, ParsedSection
from src.ingestion.parsers.base import BaseParser, read_text


class JsonParser(BaseParser):
    """A JSON value as one section, one "path.to.key: value" line per leaf.

    Each line carries its full key path, so a chunk from deep inside a large
    file still says what its values mean.
    """

    file_type = FileType.JSON

    def _parse(self, path: Path) -> ParsedDocument:
        text, encoding = read_text(path)
        value = json.loads(text)

        return ParsedDocument(
            sections=[ParsedSection(text="\n".join(_flatten(value, "")))],
            metadata={"encoding": encoding},
        )


def _flatten(value: Any, path: str) -> list[str]:
    if isinstance(value, dict):
        return [
            line
            for key, item in value.items()
            for line in _flatten(item, f"{path}.{key}" if path else str(key))
        ]

    if isinstance(value, list):
        return [
            line
            for index, item in enumerate(value)
            for line in _flatten(item, f"{path}[{index}]")
        ]

    # Strings print as-is; null, true, false and numbers in JSON spelling.
    text = value if isinstance(value, str) else json.dumps(value)
    return [f"{path}: {text}" if path else text]
