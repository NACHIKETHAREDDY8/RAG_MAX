import hashlib
import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

APP_NAME = os.getenv("APP_NAME", "RAG-Application")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSION = 1536
CHAT_MODEL = "gpt-4o-mini"

DOCUMENTS_DIR = Path("documents")

# Larger files are rejected before they are read.
MAX_FILE_SIZE_MB = 50

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
TOP_K = 5

# How documents are split into chunks: any name from
# src.chunking.registry.available_chunkers(). See docs/chunking.md.
CHUNKING_STRATEGY = os.getenv("CHUNKING_STRATEGY", "fixed")

# Parameters of every strategy; only the selected strategy's entry is used.
# Sizes are in characters except for the token strategy.
CHUNKING_PARAMS = {
    "fixed": {"chunk_size": CHUNK_SIZE, "overlap": CHUNK_OVERLAP},
    "sliding_window": {"window_size": 100, "step": 75},
    "sentence": {"max_chars": CHUNK_SIZE, "overlap_sentences": 1},
    "recursive": {"chunk_size": CHUNK_SIZE, "overlap": 0},
    "token": {"max_tokens": 128, "overlap_tokens": 16},
    "semantic": {
        "buffer_size": 1,
        "threshold_type": "percentile",
        "breakpoint_threshold": 85.0,
        "max_chars": 1000,
        "min_chars": 150,
        "respect_headings": True,
        "keep_references": True,
    },
    "structure": {"max_chars": 1000, "min_section_chars": 200},
    # rules and fallback default to src.chunking.metadata_aware.DEFAULT_RULES.
    "metadata_aware": {},
    "parent_child": {"parent_size": 2000, "child_size": 400, "child_overlap": 0},
    "hierarchical": {
        "section_max_chars": 3000,
        "paragraph_max_chars": 1000,
        "chunk_size": 400,
        "context_level": "section",
    },
}

# For strategies that store a larger context with each chunk (parent_child,
# hierarchical, and metadata_aware rules routing to them): answer from that
# context rather than from the matched chunk alone.
RETRIEVAL_EXPAND_CONTEXT = True

# Each strategy and parameter set gets its own index, named after a
# fingerprint of the parameters. Changing either builds a fresh index on the
# next run instead of keeping chunks cut the old way, never mixes two kinds
# of chunk in one search, and switching back costs nothing. The original
# fixed 500/50 setting keeps the original name, so indexes built before
# Phase 11 stay in use.
LEGACY_CHUNKING = ("fixed", {"chunk_size": 500, "overlap": 50})


def vector_store_path(strategy: str, params: dict) -> Path:
    if (strategy, params) == LEGACY_CHUNKING:
        return Path("vector_store.faiss")
    fingerprint = hashlib.sha256(
        json.dumps(params, sort_keys=True).encode("utf-8")
    ).hexdigest()[:8]
    return Path(f"vector_store.{strategy}-{fingerprint}.faiss")


VECTOR_STORE_PATH = vector_store_path(
    CHUNKING_STRATEGY, CHUNKING_PARAMS.get(CHUNKING_STRATEGY, {})
)

# Tenant assigned to documents whose metadata does not name one.
DEFAULT_TENANT_ID = "default"
