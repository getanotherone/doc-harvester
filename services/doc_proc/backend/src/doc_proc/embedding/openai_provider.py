"""OpenAI-compatible embedding provider.

Supports text-embedding-3-* models with Matryoshka dimensions.
"""

from __future__ import annotations

import logging

from doc_proc.embedding.base import BaseEmbeddingProvider

logger = logging.getLogger(__name__)


class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    def __init__(
        self,
        model: str = "text-embedding-3-small",
        dimension: int = 1024,
        base_url: str | None = None,
        api_key: str = "",
        batch_size: int = 64,
        max_retries: int = 3,
    ):
        self.model = model
        self._dimension = dimension
        self.batch_size = batch_size
        self.max_retries = max_retries

        from openai import AsyncOpenAI

        kwargs: dict = {"api_key": api_key, "max_retries": max_retries}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = AsyncOpenAI(**kwargs)

        # Only text-embedding-3-* supports Matryoshka dimensions
        self._supports_dimensions = "embedding-3" in model.lower()

    async def embed(self, text: str) -> list[float]:
        result = await self.embed_batch([text])
        return result[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        import asyncio

        all_embeddings: list[list[float]] = []

        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]

            kwargs: dict = {"model": self.model, "input": batch}
            if self._supports_dimensions:
                kwargs["dimensions"] = self._dimension

            for attempt in range(self.max_retries):
                try:
                    response = await self._client.embeddings.create(**kwargs)
                    # Guarantee ordering
                    sorted_data = sorted(response.data, key=lambda x: x.index)
                    all_embeddings.extend([d.embedding for d in sorted_data])
                    break
                except Exception as e:
                    if attempt == self.max_retries - 1:
                        raise
                    wait = 2 ** attempt
                    logger.warning(
                        "OpenAI embed batch error (attempt %d/%d): %s, retrying in %ds",
                        attempt + 1, self.max_retries, e, wait,
                    )
                    await asyncio.sleep(wait)

        return all_embeddings

    def dimension(self) -> int:
        return self._dimension
