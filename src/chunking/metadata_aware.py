from typing import TYPE_CHECKING, Any

from src.chunking.base import Chunker
from src.chunking.models import Chunk

if TYPE_CHECKING:
    from src.embeddings.service import EmbeddingService

# Which strategy suits which kind of document. The first rule whose "when"
# matches the document's metadata wins; a list matches any of its values.
DEFAULT_RULES: list[dict[str, Any]] = [
    {
        # One "column: value" line per row or value: keep lines whole.
        "when": {"source_type": ["csv", "json"]},
        "strategy": "recursive",
        "params": {"chunk_size": 500, "separators": ["line", "word"]},
    },
    {
        "when": {"source_type": ["markdown", "html", "docx"]},
        "strategy": "structure",
        "params": {"max_chars": 1000},
    },
]
DEFAULT_FALLBACK: dict[str, Any] = {"strategy": "recursive", "params": {"chunk_size": 500}}


class MetadataAwareChunker(Chunker):
    """Choose the strategy for each document from its metadata.

    rules is a list of {"when": {field: value or [values]}, "strategy": name,
    "params": {...}}, tried in order against the document's metadata
    (source_type, category, department, page, ...); fallback is used when
    none matches. A tabular CSV, a Markdown handbook and a scanned-in PDF
    each get the chunking that suits them, in one index.

    Chunks record the strategy that made them as "metadata_aware:<name>".
    """

    name = "metadata_aware"

    def __init__(
        self,
        rules: list[dict[str, Any]] | None = None,
        fallback: dict[str, Any] | None = None,
        embedding_service: "EmbeddingService | None" = None,
    ) -> None:
        from src.chunking.registry import get_chunker

        self.rules = rules if rules is not None else DEFAULT_RULES
        self.fallback = fallback or DEFAULT_FALLBACK

        def build(rule: dict[str, Any]) -> Chunker:
            if rule["strategy"] == self.name:
                raise ValueError("metadata_aware cannot route to itself")
            return get_chunker(
                rule["strategy"], embedding_service=embedding_service, **rule.get("params", {})
            )

        self._chunkers = [build(rule) for rule in self.rules]
        self._fallback_chunker = build(self.fallback)
        self.provides_context = any(
            chunker.provides_context for chunker in [*self._chunkers, self._fallback_chunker]
        )

    def chunker_for(self, metadata: dict[str, Any]) -> Chunker:
        for rule, chunker in zip(self.rules, self._chunkers):
            if all(_matches(metadata.get(key), value) for key, value in rule["when"].items()):
                return chunker
        return self._fallback_chunker

    def _chunk(self, text: str, document_id: str, metadata: dict, prefix: str) -> list[Chunk]:
        chunker = self.chunker_for(metadata)
        chunks = chunker.chunk(text, document_id, metadata, prefix)
        for chunk in chunks:
            chunk.strategy = f"{self.name}:{chunker.name}"
        return chunks


def _matches(actual: Any, expected: Any) -> bool:
    if isinstance(expected, list):
        return actual in expected
    return actual == expected
