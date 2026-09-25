from src.vector_store.base import VectorStore
from src.vector_store.models import SearchResult, VectorRecord

# Implementations such as FAISSVectorStore are imported from their own module,
# so code that depends only on the interface never loads a specific backend.
__all__ = [
    "VectorStore",
    "VectorRecord",
    "SearchResult",
]
