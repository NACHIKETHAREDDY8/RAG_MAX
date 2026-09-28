"""Look up chunking strategies by name, so configuration picks the strategy."""

import inspect
from typing import TYPE_CHECKING, Any

from src.chunking.base import Chunker
from src.chunking.fixed import FixedSizeChunker
from src.chunking.hierarchical import HierarchicalChunker
from src.chunking.metadata_aware import MetadataAwareChunker
from src.chunking.parent_child import ParentChildChunker
from src.chunking.recursive import RecursiveChunker
from src.chunking.semantic import SemanticChunker
from src.chunking.sentence import SentenceChunker
from src.chunking.sliding_window import SlidingWindowChunker
from src.chunking.structure import StructureChunker
from src.chunking.token import TokenChunker

if TYPE_CHECKING:
    from src.embeddings.service import EmbeddingService

_CHUNKERS: dict[str, type[Chunker]] = {
    chunker.name: chunker
    for chunker in (
        FixedSizeChunker,
        SlidingWindowChunker,
        SentenceChunker,
        RecursiveChunker,
        TokenChunker,
        SemanticChunker,
        StructureChunker,
        MetadataAwareChunker,
        ParentChildChunker,
        HierarchicalChunker,
    )
}
_ALIASES = {"markdown": "structure", "fixed_size": "fixed", "parent-child": "parent_child"}


def register_chunker(chunker: type[Chunker]) -> type[Chunker]:
    """Make a new strategy available by its name. Usable as a class decorator."""
    _CHUNKERS[chunker.name] = chunker
    return chunker


def available_chunkers() -> list[str]:
    return sorted(_CHUNKERS)


def get_chunker(
    name: str,
    embedding_service: "EmbeddingService | None" = None,
    **params: Any,
) -> Chunker:
    """Build the named strategy with the given parameters.

    embedding_service is passed to strategies that take one (semantic, and
    metadata_aware for rules that route to semantic) and ignored otherwise.
    """
    key = _ALIASES.get(name, name)
    if key not in _CHUNKERS:
        raise ValueError(
            f"Unknown chunking strategy '{name}'. Available: {', '.join(available_chunkers())}"
        )

    chunker_class = _CHUNKERS[key]
    if "embedding_service" in inspect.signature(chunker_class.__init__).parameters:
        if embedding_service is None and key == SemanticChunker.name:
            raise ValueError("The semantic strategy needs an embedding_service.")
        params["embedding_service"] = embedding_service

    return chunker_class(**params)


def build_chunker(
    strategy: str,
    params_by_strategy: dict[str, dict[str, Any]],
    embedding_service: "EmbeddingService | None" = None,
) -> Chunker:
    """Build a strategy using its entry in a {strategy: params} settings table."""
    key = _ALIASES.get(strategy, strategy)
    return get_chunker(key, embedding_service, **params_by_strategy.get(key, {}))
