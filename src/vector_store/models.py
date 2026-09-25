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
