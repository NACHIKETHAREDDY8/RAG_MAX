"""Construct the application's services and connect them."""

from dataclasses import dataclass

import config
from src.embeddings.provider import OpenAIEmbeddingProvider
from src.embeddings.service import EmbeddingService
from src.generation.llm import OpenAILLM
from src.generation.service import GenerationService
from src.indexing.service import IndexingService
from src.repositories.vector_store_repository import VectorStoreRepository
from src.retrieval.service import RetrievalService
from src.services.rag_service import RAGService
from src.vector_store.faiss_store import FAISSVectorStore


@dataclass(frozen=True)
class Container:
    indexing_service: IndexingService
    rag_service: RAGService


def build_container() -> Container:
    """Build every service from the settings in config.py."""
    embedding_service = EmbeddingService(
        OpenAIEmbeddingProvider(
            api_key=config.OPENAI_API_KEY,
            model=config.EMBEDDING_MODEL,
        ),
        dimension=config.EMBEDDING_DIMENSION,
    )
    repository = VectorStoreRepository(
        FAISSVectorStore.load_or_create(
            config.VECTOR_STORE_PATH,
            dimension=config.EMBEDDING_DIMENSION,
        ),
        config.VECTOR_STORE_PATH,
    )

    indexing_service = IndexingService(
        embedding_service,
        repository,
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP,
    )
    rag_service = RAGService(
        RetrievalService(embedding_service, repository, top_k=config.TOP_K),
        GenerationService(
            OpenAILLM(api_key=config.OPENAI_API_KEY, model=config.CHAT_MODEL)
        ),
    )

    return Container(indexing_service=indexing_service, rag_service=rag_service)
