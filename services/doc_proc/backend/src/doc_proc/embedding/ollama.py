"""Ollama embedding provider — BGE-M3 via /api/embed endpoint.

Sequential sub-batches to protect GPU. Exponential backoff retry.
"""

from __future__ import annotations

import asyncio
import logging

import httpx

from doc_proc.embedding.base import BaseEmbeddingProvider

logger = logging.getLogger(__name__)


class OllamaEmbeddingProvider(BaseEmbeddingProvider):
    def __init__(
        self,
        model: str = "bge-m3",
        dimension: int = 1024,
        base_url: str = "http://host.docker.internal:11434",
        batch_size: int = 64,
        concurrency: int = 1,
        timeout: float = 180.0,
        max_retries: int = 3,
    ):
        self.model = model
        self._dimension = dimension
        self.base_url = base_url.rstrip("/")
        self.batch_size = batch_size
        self._semaphore = asyncio.Semaphore(concurrency)
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout),
            )
        return self._client

    async def embed(self, text: str) -> list[float]:
        result = await self.embed_batch([text])
        return result[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        all_embeddings: list[list[float]] = []

        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            async with self._semaphore:
                embeddings = await self._embed_with_retry(batch)
                all_embeddings.extend(embeddings)

        return all_embeddings

    async def _embed_with_retry(self, texts: list[str]) -> list[list[float]]:
        client = self._get_client()
        last_error: Exception | None = None

        for attempt in range(self.max_retries):
            try:
                response = await client.post(
                    "/api/embed",
                    json={"model": self.model, "input": texts},
                )
                response.raise_for_status()
                data = response.json()

                embeddings = data.get("embeddings", [])
                if not embeddings:
                    raise ValueError("Empty embedding response")

                # Validate dimension
                if embeddings[0] and len(embeddings[0]) != self._dimension:
                    raise ValueError(
                        f"Dimension mismatch: expected {self._dimension}, "
                        f"got {len(embeddings[0])}. Check embedding_dimension setting."
                    )

                return embeddings

            except (httpx.ConnectError, httpx.ConnectTimeout) as e:
                raise RuntimeError(
                    f"Cannot connect to Ollama at {self.base_url}. "
                    "Is Ollama running? Start with: ollama serve"
                ) from e
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    raise RuntimeError(
                        f"Model '{self.model}' not found. "
                        f"Pull it with: ollama pull {self.model}"
                    ) from e
                last_error = e
            except Exception as e:
                last_error = e

            if attempt < self.max_retries - 1:
                wait = 2**attempt
                logger.warning(
                    "Embed attempt %d failed: %s. Retrying in %ds...",
                    attempt + 1, last_error, wait,
                )
                await asyncio.sleep(wait)

        raise RuntimeError(f"Embedding failed after {self.max_retries} attempts: {last_error}")

    def dimension(self) -> int:
        return self._dimension

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
