import pytest
import json
import time
import os
import sys
from unittest.mock import AsyncMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# -- Cache tests -----------------------------------------------------------


class TestTTLCache:

    def test_set_and_get(self):
        from shared.cache import TTLCache

        cache = TTLCache(ttl_seconds=300)
        cache.set("key1", {"value": 42})
        result = cache.get("key1")
        assert result == {"value": 42}

    def test_miss_returns_none(self):
        from shared.cache import TTLCache

        cache = TTLCache(ttl_seconds=300)
        assert cache.get("nonexistent") is None

    def test_expired_returns_none(self):
        from shared.cache import TTLCache

        cache = TTLCache(ttl_seconds=0)
        cache.set("key1", {"value": 42})
        time.sleep(0.01)
        assert cache.get("key1") is None

    def test_overwrite(self):
        from shared.cache import TTLCache

        cache = TTLCache(ttl_seconds=300)
        cache.set("key1", {"value": 1})
        cache.set("key1", {"value": 2})
        assert cache.get("key1") == {"value": 2}

    def test_delete(self):
        from shared.cache import TTLCache

        cache = TTLCache(ttl_seconds=300)
        cache.set("key1", {"value": 1})
        cache.delete("key1")
        assert cache.get("key1") is None

    def test_clear(self):
        from shared.cache import TTLCache

        cache = TTLCache(ttl_seconds=300)
        cache.set("k1", 1)
        cache.set("k2", 2)
        cache.clear()
        assert cache.get("k1") is None
        assert cache.get("k2") is None

    def test_ttl_per_key(self):
        from shared.cache import TTLCache

        cache = TTLCache(ttl_seconds=300)
        cache.set("long", "keep", ttl_override=300)
        cache.set("short", "drop", ttl_override=0)
        time.sleep(0.01)
        assert cache.get("long") == "keep"
        assert cache.get("short") is None


# -- Intent Router tests ---------------------------------------------------

MOCK_ROUTE = {
    "id": "general:full_context",
    "domain": "general",
    "intent": "full_context",
    "query_strategy": "materialized_view",
    "required_params": json.dumps(["entity_id"]),
    "optional_params": json.dumps(
        ["include_events", "include_knowledge", "knowledge_limit"]
    ),
    "defaults_json": json.dumps(
        {
            "include_events": True,
            "include_knowledge": True,
            "knowledge_limit": 5,
        }
    ),
    "vector_search_filter": None,
    "cache_ttl_seconds": 300,
}

MOCK_VIEW = {
    "id": "general:account:acct-001",
    "entity_type": "account",
    "entity_id": "acct-001",
    "domain": "general",
    "core_record": json.dumps({"name": "Alpha", "status": "active"}),
    "related_records": json.dumps([{"record_id": "rec-001"}]),
    "recent_events": json.dumps([{"date": "2026-04-20", "event": "updated"}]),
    "knowledge_hits": json.dumps([]),
    "last_refreshed": "2099-01-01T00:00:00+00:00",
    "knowledge_refresh_needed": 0,
}

MOCK_KNOWLEDGE = [
    {
        "id": "kb-001",
        "citation": "Protocol \u00a7 1.1",
        "content": "account activation requires verification",
        "confidence": "HIGH",
        "source_tier": 1,
    }
]


class TestIntentRouter:

    @pytest.mark.asyncio
    async def test_resolve_returns_assembled_result(self):
        from shared.intent_router import IntentRouter

        mock_db = AsyncMock()
        mock_db.get_route = AsyncMock(return_value=MOCK_ROUTE)
        mock_db.get_materialized_view = AsyncMock(return_value=MOCK_VIEW)
        mock_db.search_knowledge = AsyncMock(return_value=MOCK_KNOWLEDGE)

        router = IntentRouter(db=mock_db)
        result = await router.resolve(
            entity_id="acct-001",
            entity_type="account",
            intent="full_context",
            domain="general",
        )
        assert result is not None
        assert "entity" in result
        assert "assembled_sources" in result
        assert len(result["assembled_sources"]) >= 1

    @pytest.mark.asyncio
    async def test_resolve_includes_knowledge_hits(self):
        from shared.intent_router import IntentRouter

        mock_db = AsyncMock()
        mock_db.get_route = AsyncMock(return_value=MOCK_ROUTE)
        mock_db.get_materialized_view = AsyncMock(return_value=MOCK_VIEW)
        mock_db.search_knowledge = AsyncMock(return_value=MOCK_KNOWLEDGE)

        router = IntentRouter(db=mock_db)
        result = await router.resolve(
            entity_id="acct-001",
            entity_type="account",
            intent="full_context",
            domain="general",
            include_knowledge=True,
        )
        assert "knowledge_hits" in result
        assert len(result["knowledge_hits"]) == 1
        mock_db.search_knowledge.assert_called_once()

    @pytest.mark.asyncio
    async def test_resolve_skips_knowledge_when_disabled(self):
        from shared.intent_router import IntentRouter

        mock_db = AsyncMock()
        mock_db.get_route = AsyncMock(return_value=MOCK_ROUTE)
        mock_db.get_materialized_view = AsyncMock(return_value=MOCK_VIEW)
        mock_db.search_knowledge = AsyncMock(return_value=[])

        router = IntentRouter(db=mock_db)
        result = await router.resolve(
            entity_id="acct-001",
            entity_type="account",
            intent="full_context",
            domain="general",
            include_knowledge=False,
        )
        mock_db.search_knowledge.assert_not_called()

    @pytest.mark.asyncio
    async def test_unknown_intent_returns_none(self):
        from shared.intent_router import IntentRouter

        mock_db = AsyncMock()
        mock_db.get_route = AsyncMock(return_value=None)

        router = IntentRouter(db=mock_db)
        result = await router.resolve(
            entity_id="acct-001",
            entity_type="account",
            intent="nonexistent_intent",
            domain="general",
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_stale_view_triggers_fallback(self):
        from shared.intent_router import IntentRouter

        stale_view = dict(MOCK_VIEW)
        stale_view["last_refreshed"] = "2020-01-01T00:00:00+00:00"

        mock_db = AsyncMock()
        mock_db.get_route = AsyncMock(return_value=MOCK_ROUTE)
        mock_db.get_materialized_view = AsyncMock(return_value=stale_view)
        mock_db.upsert_materialized_view = AsyncMock()

        router = IntentRouter(db=mock_db)
        result = await router.resolve(
            entity_id="acct-001",
            entity_type="account",
            intent="full_context",
            domain="general",
        )
        assert result is not None
        assert result.get("stale") is True

    @pytest.mark.asyncio
    async def test_assembled_sources_contains_view_ref(self):
        from shared.intent_router import IntentRouter

        mock_db = AsyncMock()
        mock_db.get_route = AsyncMock(return_value=MOCK_ROUTE)
        mock_db.get_materialized_view = AsyncMock(return_value=MOCK_VIEW)
        mock_db.search_knowledge = AsyncMock(return_value=[])

        router = IntentRouter(db=mock_db)
        result = await router.resolve(
            entity_id="acct-001",
            entity_type="account",
            intent="full_context",
            domain="general",
        )
        sources = result["assembled_sources"]
        assert any("materialized_view" in s for s in sources)

    @pytest.mark.asyncio
    async def test_route_cached_after_first_load(self):
        from shared.intent_router import IntentRouter

        mock_db = AsyncMock()
        mock_db.get_route = AsyncMock(return_value=MOCK_ROUTE)
        mock_db.get_materialized_view = AsyncMock(return_value=MOCK_VIEW)
        mock_db.search_knowledge = AsyncMock(return_value=[])

        router = IntentRouter(db=mock_db)
        await router.resolve("acct-001", "account", "full_context", "general")
        await router.resolve("acct-001", "account", "full_context", "general")
        assert mock_db.get_route.call_count == 1


# -- Attestation tests -----------------------------------------------------


class TestAttestation:

    @pytest.mark.asyncio
    async def test_write_creates_record(self):
        from shared.attestation import Attestation

        mock_db = AsyncMock()
        mock_db.write_attestation = AsyncMock()

        attestation = Attestation(db=mock_db)
        record_id = await attestation.write(
            session_id="sess-001",
            tool_name="get_entity_context",
            intent="full_context",
            domain="general",
            entity_id="acct-001",
            assembled_sources=["view::acct-001", "fts::kb-001"],
            result_payload={"entity": {"name": "Alpha"}},
            latency_ms=42,
        )
        assert record_id is not None
        assert isinstance(record_id, str)
        mock_db.write_attestation.assert_called_once()

    @pytest.mark.asyncio
    async def test_result_hash_is_sha256(self):
        import hashlib
        from shared.attestation import Attestation

        mock_db = AsyncMock()
        mock_db.write_attestation = AsyncMock()

        attestation = Attestation(db=mock_db)
        payload = {"entity": {"name": "Alpha"}}
        await attestation.write(
            session_id="sess-001",
            tool_name="get_entity_context",
            intent="full_context",
            domain="general",
            entity_id="acct-001",
            assembled_sources=[],
            result_payload=payload,
            latency_ms=10,
        )
        call_args = mock_db.write_attestation.call_args[0][0]
        expected_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode()
        ).hexdigest()
        assert call_args["result_hash"] == expected_hash

    @pytest.mark.asyncio
    async def test_record_contains_all_required_fields(self):
        from shared.attestation import Attestation

        mock_db = AsyncMock()
        mock_db.write_attestation = AsyncMock()

        attestation = Attestation(db=mock_db)
        await attestation.write(
            session_id="sess-001",
            tool_name="get_entity_context",
            intent="full_context",
            domain="general",
            entity_id="acct-001",
            assembled_sources=["view::acct-001"],
            result_payload={"entity": {}},
            latency_ms=25,
        )
        record = mock_db.write_attestation.call_args[0][0]
        for field in [
            "id",
            "session_id",
            "tool_name",
            "tool_type",
            "intent",
            "domain",
            "entity_id",
            "assembled_sources",
            "result_hash",
            "timestamp",
            "latency_ms",
        ]:
            assert field in record, f"Missing field: {field}"
