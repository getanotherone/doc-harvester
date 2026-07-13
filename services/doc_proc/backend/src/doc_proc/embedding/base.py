"""Base class for embedding providers."""

from abc import ABC, abstractmethod


class BaseEmbeddingProvider(ABC):
    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        ...

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        ...

    @abstractmethod
    def dimension(self) -> int:
        ...
