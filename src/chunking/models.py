from dataclasses import dataclass, field
from typing import Any

# Keys the chunker, not the document, contributes to a stored chunk's
# metadata. A metadata refresh rebuilds the document's part and keeps these.
CHUNK_METADATA_KEYS = frozenset(
    {
        "chunk_strategy",
        "chunk_start",
        "chunk_end",
        "chunk_level",
        "parent_id",
        "context_id",
        "context_text",
        "section_path",
    }
)


@dataclass
class Chunk:
    """One piece of a document, as produced by any Chunker.

    start and end are character offsets into the text the chunker was given,
    so text == source[start:end] unless the strategy prepends context (the
    structure chunker's section path). Chunks created before Phase 11 leave
    every optional field unset.
    """

    chunk_id: str
    document_id: str
    text: str
    chunk_index: int
    metadata: dict[str, Any] = field(default_factory=dict)
    start: int | None = None
    end: int | None = None
    strategy: str | None = None
    # The chunk one level up in the same chunker's output (parent-child,
    # hierarchical), or None for top-level chunks.
    parent_id: str | None = None
    level: int | None = None
    # False for chunks that exist only to give context (parents, sections):
    # they are not embedded or searched.
    retrievable: bool = True
    # A larger surrounding chunk to hand to the LLM in place of text when
    # retrieval expands matches to their context.
    context_id: str | None = None
    context: str | None = None

    def stored_metadata(self) -> dict[str, Any]:
        """Return the metadata to store with this chunk's vector."""
        fields = {
            "chunk_strategy": self.strategy,
            "chunk_start": self.start,
            "chunk_end": self.end,
            "chunk_level": self.level,
            "parent_id": self.parent_id,
            "context_id": self.context_id,
            "context_text": self.context,
        }
        return {
            **self.metadata,
            **{key: value for key, value in fields.items() if value is not None},
            "document_id": self.document_id,
        }
