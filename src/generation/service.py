"""Generation service orchestration for the answer-generation phase."""

from src.embeddings.service import EmbeddingService
from src.generation.llm import OpenAILLM
from src.generation.prompt import build_rag_prompt
from src.vector_store.base import VectorStore
from src.vector_store.models import SearchResult


class RAGService:
	"""Coordinate retrieval and grounded answer generation."""

	def __init__(
		self,
		embedding_service: EmbeddingService,
		vector_store: VectorStore,
		llm: OpenAILLM,
	) -> None:
		self.embedding_service = embedding_service
		self.vector_store = vector_store
		self.llm = llm

	def retrieve(self, question: str, top_k: int = 5) -> list[SearchResult]:
		"""Embed a question and retrieve its most similar chunks."""
		query_embedding = self.embedding_service.embed_query(question)
		return self.vector_store.search(query_embedding, top_k=top_k)

	def answer(self, question: str, top_k: int = 5) -> str:
		"""Retrieve context, build a grounded prompt, and generate an answer."""
		answer, _ = self.answer_with_context(question, top_k=top_k)
		return answer

	def answer_with_context(
		self,
		question: str,
		top_k: int = 5,
	) -> tuple[str, list[SearchResult]]:
		"""Generate an answer and return the retrieved context used."""
		context = self.retrieve(question, top_k=top_k)
		prompt = build_rag_prompt(question, context)
		return self.llm.generate(prompt), context
