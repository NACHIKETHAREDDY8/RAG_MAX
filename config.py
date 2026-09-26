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
VECTOR_STORE_PATH = Path("vector_store.faiss")

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
TOP_K = 5

# Tenant assigned to documents whose metadata does not name one.
DEFAULT_TENANT_ID = "default"
