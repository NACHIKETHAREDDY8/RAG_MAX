"""LLM provider abstractions for the answer-generation phase."""

from abc import ABC, abstractmethod

from openai import OpenAI

import config


class LLM(ABC):
    """Interface for models that answer a prompt."""

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Send a prompt to the model and return its answer."""


class OpenAILLM(LLM):
    """Generate answers with an OpenAI chat-completions model."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = config.CHAT_MODEL,
        client: OpenAI | None = None,
    ) -> None:
        self.model = model
        self.client = client or OpenAI(api_key=api_key or config.OPENAI_API_KEY)

    def generate(self, prompt: str) -> str:
        """Send a prompt to the LLM and return its answer."""
        if not prompt.strip():
            raise ValueError("Prompt must not be empty.")

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
        )
        answer = response.choices[0].message.content

        if not answer:
            raise ValueError("LLM returned an empty answer.")

        return answer.strip()
