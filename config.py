import os

from dotenv import load_dotenv

load_dotenv()

APP_NAME = os.getenv("APP_NAME", "RAG-Application")
ENVIRONMENT = os.getenv("ENVIRONMENT", "-development")
LOG_LEVEL = os.getenv("LOG_LEVEL", "-INFO")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSION = 1536