"""
MCP-DB — embedding provider abstraction.

``get_embedder(provider=None)`` returns an async ``embed(text) -> list[float]``
selected by the ``EMBED_PROVIDER`` env var. This lets the graph/vector path take
a text ``intent`` and turn it into a query vector, while keeping the repo's core
dependency-free and offline (see CLAUDE.md settled decisions: SQLite variant runs
offline with no extra deps; MIT-only).

Providers:
  hash        (default) dependency-free hashing vectorizer — deterministic,
              offline, gives real (lexical) cosine similarity. Dimension is
              ``EMBED_DIM`` (default 384). This is the CI/test default so the
              repo needs no model download or API key to run.
  openai      OpenAI text-embedding-3-small (1536-dim). Lazy — requires
              OPENAI_API_KEY; raises a clear error if unavailable.
  local       sentence-transformers all-MiniLM-L6-v2 (384-dim). Lazy OPTIONAL
              dependency — raises a clear error if the package is not installed.
  passthrough caller supplies precomputed vectors; the embedder itself refuses
              to embed text (use the query_vector argument instead).

Note (deviation from the original build spec): the spec named sqlite-vec and
sentence-transformers as core deps with a 1536-dim default. mcp-db's CLAUDE.md
forbids extra/offline-breaking deps, so the default here is the dependency-free
hashing embedder and the heavier providers are lazy-optional. ``EMBED_DIM`` keeps
the query dimension aligned with whatever dimension the stored node vectors use.
"""

from __future__ import annotations

import hashlib
import math
import os
import re
from typing import Awaitable, Callable

DEFAULT_EMBED_DIM = 384
_TOKEN_RE = re.compile(r"[a-z0-9]+")

Embedder = Callable[[str], Awaitable[list[float]]]


def embed_dim() -> int:
    """Configured embedding dimension (``EMBED_DIM`` env, default 384)."""
    raw = os.environ.get("EMBED_DIM")
    return int(raw) if raw else DEFAULT_EMBED_DIM


def hash_embed(text: str, dim: int | None = None) -> list[float]:
    """Deterministic, dependency-free hashing vectorizer.

    Each token is hashed (blake2b) into one of ``dim`` buckets with a signed
    contribution; the vector is L2-normalized. Identical text always yields an
    identical vector, and overlapping text yields high cosine similarity — enough
    for a reference implementation and offline tests, with no model or network.
    """
    d = dim or embed_dim()
    vec = [0.0] * d
    for token in _TOKEN_RE.findall((text or "").lower()):
        h = int.from_bytes(
            hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest(), "big"
        )
        idx = h % d
        sign = 1.0 if (h >> 63) & 1 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0.0:
        vec = [v / norm for v in vec]
    return vec


async def _hash_embedder(text: str) -> list[float]:
    return hash_embed(text)


async def _passthrough_embedder(text: str) -> list[float]:
    raise RuntimeError(
        "EMBED_PROVIDER=passthrough does not embed text — pass a precomputed "
        "query_vector to query_graph instead of an intent string."
    )


def _make_openai_embedder() -> Embedder:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "EMBED_PROVIDER=openai requires OPENAI_API_KEY in the environment."
        )
    model = os.environ.get("OPENAI_EMBED_MODEL", "text-embedding-3-small")

    async def _embed(text: str) -> list[float]:
        import aiohttp

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.openai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"input": text, "model": model},
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
        return data["data"][0]["embedding"]

    return _embed


def _make_local_embedder() -> Embedder:
    try:
        from sentence_transformers import SentenceTransformer
    except Exception as exc:  # noqa: BLE001 — surface a clear, actionable message
        raise RuntimeError(
            "EMBED_PROVIDER=local requires the optional 'sentence-transformers' "
            "package (not a core dependency). pip install sentence-transformers."
        ) from exc

    model_name = os.environ.get("LOCAL_EMBED_MODEL", "all-MiniLM-L6-v2")
    model = SentenceTransformer(model_name)

    async def _embed(text: str) -> list[float]:
        return model.encode(text).tolist()

    return _embed


def get_embedder(provider: str | None = None) -> Embedder:
    """Return an async ``embed(text) -> list[float]`` for the selected provider."""
    name = (provider or os.environ.get("EMBED_PROVIDER") or "hash").lower()
    if name == "hash":
        return _hash_embedder
    if name == "passthrough":
        return _passthrough_embedder
    if name == "openai":
        return _make_openai_embedder()
    if name == "local":
        return _make_local_embedder()
    raise ValueError(
        f"Unknown EMBED_PROVIDER='{name}'. "
        "Supported: hash (default), openai, local, passthrough."
    )
