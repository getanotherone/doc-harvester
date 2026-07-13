"""Tests for fake embedding provider."""

import pytest

from doc_proc.embedding.fake import FakeEmbeddingProvider


class TestFakeProvider:
    @pytest.mark.asyncio
    async def test_embed_dimension(self):
        provider = FakeEmbeddingProvider(dimension=128)
        result = await provider.embed("test text")
        assert len(result) == 128
        assert provider.dimension() == 128

    @pytest.mark.asyncio
    async def test_embed_deterministic(self):
        provider = FakeEmbeddingProvider()
        v1 = await provider.embed("hello")
        v2 = await provider.embed("hello")
        assert v1 == v2

    @pytest.mark.asyncio
    async def test_embed_different_texts(self):
        provider = FakeEmbeddingProvider()
        v1 = await provider.embed("hello")
        v2 = await provider.embed("world")
        assert v1 != v2

    @pytest.mark.asyncio
    async def test_embed_batch(self):
        provider = FakeEmbeddingProvider(dimension=64)
        results = await provider.embed_batch(["a", "b", "c"])
        assert len(results) == 3
        assert all(len(v) == 64 for v in results)

    @pytest.mark.asyncio
    async def test_call_log(self):
        provider = FakeEmbeddingProvider()
        await provider.embed("one")
        await provider.embed_batch(["two", "three"])
        assert provider.call_log == ["one", "two", "three"]
