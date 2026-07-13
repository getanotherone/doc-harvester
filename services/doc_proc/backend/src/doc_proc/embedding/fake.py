"""Fake embedding provider for deterministic testing."""

from __future__ import annotations

import hashlib

from doc_proc.embedding.base import BaseEmbeddingProvider


class FakeEmbeddingProvider(BaseEmbeddingProvider):
    def __init__(self, dimension: int = 1024):
        self._dimension = dimension
        self.call_log: list[str] = []

    async def embed(self, text: str) -> list[float]:
        self.call_log.append(text)
        return self._deterministic_vector(text)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        self.call_log.extend(texts)
        return [self._deterministic_vector(t) for t in texts]

    def dimension(self) -> int:
        return self._dimension

    def _deterministic_vector(self, text: str) -> list[float]:
        h = hashlib.sha256(text.encode("utf-8")).digest()
        return [((h[i % len(h)] / 255.0) * 2 - 1) for i in range(self._dimension)]
