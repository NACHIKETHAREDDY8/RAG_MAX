from openai import OpenAI

import config
from src.embeddings.base import EmbeddingProvider


class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        api_key: str | None = None,
        model: str = config.EMBEDDING_MODEL,
        client: OpenAI | None = None,
    ) -> None:
        self.model = model
        self.client = client or OpenAI(api_key=api_key or config.OPENAI_API_KEY)

    def embed(self, text: str) -> list[float]:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        response = self.client.embeddings.create(
            input=texts,
            model=self.model,
        )

        embeddings = sorted(response.data, key=lambda item: item.index)
        return [item.embedding for item in embeddings]
