"""
MCP-DB embeddings abstraction tests.

Covers the dependency-free default (hash) embedder and the provider selector.
The openai/local providers are lazy and optional — we assert they fail with a
clear error when their prerequisites are absent, without importing them.
"""

import math
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _cos(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


class TestHashEmbedder:

    @pytest.mark.asyncio
    async def test_default_provider_is_hash(self):
        from shared.embeddings import get_embedder, hash_embed

        embed = get_embedder()
        got = await embed("the entropy fabric")
        assert got == hash_embed("the entropy fabric")

    @pytest.mark.asyncio
    async def test_hash_is_deterministic(self):
        from shared.embeddings import get_embedder

        embed = get_embedder("hash")
        assert await embed("same text") == await embed("same text")

    def test_hash_dim_matches_embed_dim(self, monkeypatch):
        from shared.embeddings import embed_dim, hash_embed

        monkeypatch.setenv("EMBED_DIM", "128")
        assert embed_dim() == 128
        assert len(hash_embed("hello world")) == 128

    def test_overlapping_text_closer_than_disjoint(self):
        from shared.embeddings import hash_embed

        base = hash_embed("azure cosmos vector graph traversal")
        near = hash_embed("azure cosmos vector graph query")
        far = hash_embed("quarterly revenue projections phoenix")
        assert _cos(base, near) > _cos(base, far)

    def test_empty_text_is_zero_vector(self):
        from shared.embeddings import hash_embed

        assert set(hash_embed("")) == {0.0}


class TestProviderSelection:

    def test_unknown_provider_raises(self):
        from shared.embeddings import get_embedder

        with pytest.raises(ValueError):
            get_embedder("nope")

    @pytest.mark.asyncio
    async def test_passthrough_refuses_to_embed(self):
        from shared.embeddings import get_embedder

        embed = get_embedder("passthrough")
        with pytest.raises(RuntimeError):
            await embed("should not embed")

    def test_openai_without_key_raises_clear(self, monkeypatch):
        from shared.embeddings import get_embedder

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
            get_embedder("openai")

    def test_local_without_package_raises_clear(self):
        import importlib.util

        from shared.embeddings import get_embedder

        if importlib.util.find_spec("sentence_transformers") is not None:
            pytest.skip("sentence-transformers installed; skip missing-dep path")
        with pytest.raises(RuntimeError, match="sentence-transformers"):
            get_embedder("local")
