from dataclasses import dataclass, field
from typing import Any


@dataclass
class VectorRecord:
    chunk_id: str
    text: str
    embedding: list[float]
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class SearchResult:
    chunk_id: str
    text: str
    metadata: dict[str, Any]
    score: float

    @property
    def filename(self) -> str | None:
        # Records indexed before Phase 9 stored the filename as "source".
        return self.metadata.get("filename", self.metadata.get("source"))

    @property
    def page(self) -> int | None:
        return self.metadata.get("page")

    @property
    def document_id(self) -> str | None:
        return self.metadata.get("document_id")
