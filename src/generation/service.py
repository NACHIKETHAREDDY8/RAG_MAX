"""Generation service orchestration for the answer-generation phase."""

from src.generation.llm import LLM
from src.generation.prompt import build_rag_prompt
from src.vector_store.models import SearchResult


class GenerationService:
    """Generate a grounded answer from a question and retrieved context."""

    def __init__(self, llm: LLM) -> None:
        self.llm = llm

    def generate(self, question: str, context: list[SearchResult]) -> str:
        """Build a grounded prompt and return the LLM's answer."""
        prompt = build_rag_prompt(question, context)
        return self.llm.generate(prompt)
