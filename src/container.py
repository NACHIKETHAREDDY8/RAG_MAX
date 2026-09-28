"""Construct the application's services and connect them."""

from dataclasses import dataclass

import config
from src.chunking.registry import build_chunker
from src.embeddings.provider import OpenAIEmbeddingProvider
from src.embeddings.service import EmbeddingService
from src.generation.llm import OpenAILLM
from src.generation.service import GenerationService
from src.indexing.service import IndexingService
from src.ingestion.pipeline import IngestionPipeline
from src.repositories.vector_store_repository import VectorStoreRepository
from src.retrieval.service import RetrievalService
from src.services.rag_service import RAGService
from src.vector_store.faiss_store import FAISSVectorStore


@dataclass(frozen=True)
class Container:
    ingestion_pipeline: IngestionPipeline
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

    # The index file is named after this entry's parameters, so the strategy
    # must be spelled as its key (an alias would fingerprint the wrong entry).
    if config.CHUNKING_STRATEGY not in config.CHUNKING_PARAMS:
        raise ValueError(
            f"CHUNKING_STRATEGY '{config.CHUNKING_STRATEGY}' has no entry in "
            f"CHUNKING_PARAMS. Use one of: {', '.join(sorted(config.CHUNKING_PARAMS))}"
        )
    chunker = build_chunker(
        config.CHUNKING_STRATEGY,
        config.CHUNKING_PARAMS,
        embedding_service=embedding_service,
    )
    indexing_service = IndexingService(embedding_service, repository, chunker=chunker)
    rag_service = RAGService(
        RetrievalService(
            embedding_service,
            repository,
            top_k=config.TOP_K,
            expand_context=config.RETRIEVAL_EXPAND_CONTEXT and chunker.provides_context,
        ),
        GenerationService(
            OpenAILLM(api_key=config.OPENAI_API_KEY, model=config.CHAT_MODEL)
        ),
    )

    ingestion_pipeline = IngestionPipeline(
        max_file_size_bytes=config.MAX_FILE_SIZE_MB * 1024 * 1024,
    )

    return Container(
        ingestion_pipeline=ingestion_pipeline,
        indexing_service=indexing_service,
        rag_service=rag_service,
    )
