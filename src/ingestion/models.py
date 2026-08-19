from dataclasses import dataclass, field


@dataclass
class Document:
    document_id: str
    source: str
    filename: str
    page_number: int
    text: str
    metadata: dict = field(default_factory=dict)
    