import pytest

from src.chunking.models import Chunk
from src.embeddings.base import EmbeddingProvider
from src.embeddings.service import EmbeddingService
from src.ingestion.models import Document
from src.repositories.vector_store_repository import VectorStoreRepository
from src.vector_store.faiss_store import FAISSVectorStore


KEYWORDS = ["cat", "dog", "fish"]


class FakeEmbeddingProvider(EmbeddingProvider):
    """Embed text as keyword counts so similarity is predictable offline."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed(self, text: str) -> list[float]:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [
            [text.lower().count(keyword) + 0.01 for keyword in KEYWORDS]
            for text in texts
        ]


class FakeLLM:
    def __init__(self, answer: str = "fake answer") -> None:
        self.answer = answer
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.answer


def make_chunk(document_id: str, index: int, text: str) -> Chunk:
    return Chunk(
        chunk_id=f"{document_id}_chunk_{index}",
        document_id=document_id,
        text=text,
        chunk_index=index,
        metadata={"source": "animals.pdf", "page": 1},
    )


def make_document(text: str) -> Document:
    return Document(
        document_id="hash-1",
        source="documents/animals.pdf",
        filename="animals.pdf",
        page_number=2,
        text=text,
        metadata={"file_size": 10, "file_type": ".pdf"},
    )


@pytest.fixture
def embedding_provider() -> FakeEmbeddingProvider:
    return FakeEmbeddingProvider()


@pytest.fixture
def embedding_service(embedding_provider) -> EmbeddingService:
    return EmbeddingService(embedding_provider, dimension=len(KEYWORDS))


@pytest.fixture
def repository(tmp_path) -> VectorStoreRepository:
    return VectorStoreRepository(
        FAISSVectorStore(dimension=len(KEYWORDS)),
        tmp_path / "store.faiss",
    )
