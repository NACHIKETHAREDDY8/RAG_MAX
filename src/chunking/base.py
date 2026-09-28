from abc import ABC, abstractmethod
from typing import Any, ClassVar

from src.chunking.models import Chunk
from src.chunking.spans import Span


class Chunker(ABC):
    """Split one document's text into Chunks.

    Every strategy has the same contract: blank text gives no chunks, chunk
    ids are "<prefix>_chunk_<n>" numbered from 0 in document order, every
    chunk gets its own copy of metadata, and start/end locate the chunk in
    the text. Strategies that also return context-only chunks (parents,
    sections) mark them retrievable=False and give them different id stems.
    """

    name: ClassVar[str]
    # True when retrievable chunks carry a larger context to answer from.
    provides_context: ClassVar[bool] = False

    def chunk(
        self,
        text: str,
        document_id: str,
        metadata: dict[str, Any] | None = None,
        chunk_id_prefix: str | None = None,
    ) -> list[Chunk]:
        if not text or not text.strip():
            return []

        return self._chunk(
            text,
            document_id,
            metadata or {},
            document_id if chunk_id_prefix is None else chunk_id_prefix,
        )

    @abstractmethod
    def _chunk(
        self,
        text: str,
        document_id: str,
        metadata: dict[str, Any],
        prefix: str,
    ) -> list[Chunk]:
        """Chunk non-blank text."""

    def config(self) -> dict[str, Any]:
        """Return the parameters this chunker was built with, for experiment records."""
        return {
            key: value
            for key, value in vars(self).items()
            if not key.startswith("_") and isinstance(value, (int, float, str, bool, list, dict))
        }

    def _chunks_from_spans(
        self,
        text: str,
        spans: list[Span],
        document_id: str,
        metadata: dict[str, Any],
        prefix: str,
        stem: str = "chunk",
        **fields: Any,
    ) -> list[Chunk]:
        return [
            Chunk(
                chunk_id=f"{prefix}_{stem}_{index}",
                document_id=document_id,
                text=text[start:end],
                chunk_index=index,
                metadata=metadata.copy(),
                start=start,
                end=end,
                strategy=self.name,
                **fields,
            )
            for index, (start, end) in enumerate(spans)
        ]


def require_positive(**values: int) -> None:
    for name, value in values.items():
        if value <= 0:
            raise ValueError(f"{name} must be greater than 0")


def require_overlap(overlap: int, size: int, size_name: str = "chunk_size") -> None:
    if overlap < 0:
        raise ValueError("overlap cannot be negative")
    if overlap >= size:
        raise ValueError(f"overlap must be smaller than {size_name}")
