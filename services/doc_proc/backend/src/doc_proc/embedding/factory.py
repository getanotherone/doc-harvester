"""Embedding provider factory with singleton caching."""

from __future__ import annotations

import logging

from doc_proc.config import settings
from doc_proc.embedding.base import BaseEmbeddingProvider

logger = logging.getLogger(__name__)

_cache: dict[str, BaseEmbeddingProvider] = {}


def create_embedding_provider(
    provider: str | None = None,
    **overrides,
) -> BaseEmbeddingProvider:
    """Create or return cached embedding provider.

    FakeEmbeddingProvider is never cached (preserves test isolation).
    """
    provider = provider or settings.embedding_provider
    cache_key = f"{provider}:{settings.embedding_dimension}"

    if provider == "fake":
        from doc_proc.embedding.fake import FakeEmbeddingProvider
        return FakeEmbeddingProvider(dimension=settings.embedding_dimension)

    if cache_key in _cache:
        return _cache[cache_key]

    if provider in ("ollama", "mps"):
        from doc_proc.embedding.ollama import OllamaEmbeddingProvider

        instance = OllamaEmbeddingProvider(
            model=overrides.get("model", settings.embedding_model),
            dimension=overrides.get("dimension", settings.embedding_dimension),
            base_url=overrides.get("base_url", settings.embedding_base_url),
            batch_size=overrides.get("batch_size", settings.embedding_batch_size),
            concurrency=overrides.get("concurrency", settings.embedding_concurrency),
            timeout=overrides.get("timeout", settings.embedding_timeout),
            max_retries=overrides.get("max_retries", settings.embedding_max_retries),
        )
    elif provider == "openai":
        from doc_proc.embedding.openai_provider import OpenAIEmbeddingProvider

        instance = OpenAIEmbeddingProvider(
            model=overrides.get("model", settings.embedding_model),
            dimension=overrides.get("dimension", settings.embedding_dimension),
            base_url=overrides.get("base_url", settings.embedding_base_url) or None,
            api_key=overrides.get("api_key", settings.embedding_api_key),
            batch_size=overrides.get("batch_size", settings.embedding_batch_size),
        )
    else:
        from doc_proc.embedding.fake import FakeEmbeddingProvider

        logger.warning("Unknown provider '%s', using FakeEmbeddingProvider", provider)
        return FakeEmbeddingProvider(dimension=settings.embedding_dimension)

    _cache[cache_key] = instance
    logger.info("Created %s embedding provider (dim=%d)", provider, instance.dimension())
    return instance


async def clear_cache():
    """Clear the provider cache, closing any open connections."""
    for provider in _cache.values():
        close = getattr(provider, "close", None)
        if close and callable(close):
            try:
                await close()
            except Exception:
                pass
    _cache.clear()
