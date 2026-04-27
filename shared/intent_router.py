"""
MCP-DB — Intent Router.
Core of the Compound Query Tier.

Given (entity_id, entity_type, intent, domain), resolves the compound
tool call to an assembled result payload with a source manifest.

Execution sequence:
  1. Load route from cache (or DB on miss)
  2. Point-read materialized view
  3. Staleness check — if stale, flag and return stale result
  4. Optional FTS knowledge augmentation
  5. Assemble result + assembled_sources manifest
  6. Return to caller
"""

import json
from datetime import datetime, timezone, timedelta
from typing import Any

from shared.cache import TTLCache

STALENESS_THRESHOLD_HOURS = 24


class IntentRouter:

    def __init__(self, db, route_cache: TTLCache | None = None):
        self._db = db
        self._cache = route_cache or TTLCache(ttl_seconds=300)

    async def resolve(
        self,
        entity_id: str,
        entity_type: str,
        intent: str,
        domain: str = "general",
        include_knowledge: bool = True,
        knowledge_limit: int = 5,
        include_events: bool = True,
        **kwargs: Any,
    ) -> dict | None:
        # 1. Load route (cache-first)
        route = await self._get_route(domain, intent)
        if route is None:
            return None

        # 2. Apply defaults from route
        defaults = json.loads(route.get("defaults_json", "{}"))
        _include_knowledge = include_knowledge
        _knowledge_limit = knowledge_limit or defaults.get("knowledge_limit", 5)
        _include_events = include_events

        # 3. Point-read materialized view
        view = await self._db.get_materialized_view(entity_id, entity_type)
        if view is None:
            return None

        # 4. Staleness check
        stale = self._is_stale(view.get("last_refreshed", ""))

        # 5. Optional FTS knowledge augmentation (skip if stale)
        knowledge_hits = []
        if _include_knowledge and not stale:
            knowledge_hits = await self._db.search_knowledge(
                query=domain, top=_knowledge_limit
            )

        # 6. Assemble source manifest
        assembled_sources = [f"materialized_view::{view['id']}"]
        for hit in knowledge_hits:
            assembled_sources.append(f"fts::{hit['id']}")

        # 7. Assemble result
        result = {
            "entity": json.loads(view["core_record"]),
            "records": json.loads(view.get("related_records", "[]")),
            "events": json.loads(view.get("recent_events", "[]"))
            if _include_events
            else [],
            "knowledge_hits": knowledge_hits,
            "assembled_sources": assembled_sources,
        }
        if stale:
            result["stale"] = True

        return result

    async def _get_route(self, domain: str, intent: str) -> dict | None:
        cache_key = f"route:{domain}:{intent}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        route = await self._db.get_route(domain, intent)
        if route is not None:
            ttl = route.get("cache_ttl_seconds", 300)
            self._cache.set(cache_key, route, ttl_override=ttl)
        return route

    def _is_stale(self, last_refreshed: str) -> bool:
        if not last_refreshed:
            return True
        try:
            refreshed_at = datetime.fromisoformat(last_refreshed)
            if refreshed_at.tzinfo is None:
                refreshed_at = refreshed_at.replace(tzinfo=timezone.utc)
            age = datetime.now(timezone.utc) - refreshed_at
            return age > timedelta(hours=STALENESS_THRESHOLD_HOURS)
        except ValueError:
            return True
