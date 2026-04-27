"""
MCP-DB — In-process TTL cache.
No external dependencies. Per settled decision SD-02: no Redis.

Usage:
    cache = TTLCache(ttl_seconds=300)
    cache.set("key", value)
    value = cache.get("key")   # None if expired or missing
"""

import time
from typing import Any


class TTLCache:

    def __init__(self, ttl_seconds: int = 300):
        self._default_ttl = ttl_seconds
        self._store: dict[str, tuple[Any, float]] = {}

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expiry = entry
        if time.monotonic() >= expiry:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any, ttl_override: int | None = None) -> None:
        ttl = ttl_override if ttl_override is not None else self._default_ttl
        expiry = time.monotonic() + ttl
        self._store[key] = (value, expiry)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()
