import pytest
import pytest_asyncio
import json
import os
import sys
import inspect
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# -- SQLite tests ----------------------------------------------------------

TEST_DB = "test_db_layer.sqlite"


@pytest_asyncio.fixture(autouse=True)
async def clean_test_db():
    from scripts.init_db import init_database
    from scripts.seed import seed_database

    await init_database(TEST_DB)
    await seed_database(TEST_DB)
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


class TestSQLiteDB:

    @pytest.mark.asyncio
    async def test_get_entity_exists(self):
        from shared.db_sqlite import SQLiteDB

        db = SQLiteDB(TEST_DB)
        result = await db.get_materialized_view("acct-001", "account")
        assert result is not None
        assert result["entity_id"] == "acct-001"
        assert result["domain"] == "general"
        assert isinstance(json.loads(result["core_record"]), dict)

    @pytest.mark.asyncio
    async def test_get_entity_not_found(self):
        from shared.db_sqlite import SQLiteDB

        db = SQLiteDB(TEST_DB)
        result = await db.get_materialized_view("does-not-exist", "account")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_route_exists(self):
        from shared.db_sqlite import SQLiteDB

        db = SQLiteDB(TEST_DB)
        result = await db.get_route("general", "full_context")
        assert result is not None
        assert result["intent"] == "full_context"
        assert result["query_strategy"] == "materialized_view"

    @pytest.mark.asyncio
    async def test_get_route_not_found(self):
        from shared.db_sqlite import SQLiteDB

        db = SQLiteDB(TEST_DB)
        result = await db.get_route("general", "nonexistent_intent")
        assert result is None

    @pytest.mark.asyncio
    async def test_search_knowledge_returns_results(self):
        from shared.db_sqlite import SQLiteDB

        db = SQLiteDB(TEST_DB)
        results = await db.search_knowledge("contract", top=5)
        assert len(results) >= 1
        assert all("citation" in r for r in results)
        assert all("content" in r for r in results)

    @pytest.mark.asyncio
    async def test_search_knowledge_top_limit(self):
        from shared.db_sqlite import SQLiteDB

        db = SQLiteDB(TEST_DB)
        results = await db.search_knowledge("account", top=2)
        assert len(results) <= 2

    @pytest.mark.asyncio
    async def test_search_knowledge_no_results(self):
        from shared.db_sqlite import SQLiteDB

        db = SQLiteDB(TEST_DB)
        results = await db.search_knowledge("zzznomatchzzz", top=5)
        assert results == []

    @pytest.mark.asyncio
    async def test_write_attestation_record(self):
        from shared.db_sqlite import SQLiteDB

        db = SQLiteDB(TEST_DB)
        record = {
            "id": "test-attest-001",
            "session_id": "sess-001",
            "tool_name": "get_entity_context",
            "tool_type": "compound",
            "intent": "full_context",
            "domain": "general",
            "entity_id": "acct-001",
            "assembled_sources": json.dumps(["view::acct-001", "fts::kb-001"]),
            "result_hash": "abc123",
            "timestamp": "2026-04-26T00:00:00Z",
            "latency_ms": 42,
        }
        await db.write_attestation(record)
        result = await db.get_attestation("test-attest-001")
        assert result is not None
        assert result["tool_name"] == "get_entity_context"
        assert result["latency_ms"] == 42

    @pytest.mark.asyncio
    async def test_upsert_materialized_view(self):
        from shared.db_sqlite import SQLiteDB

        db = SQLiteDB(TEST_DB)
        doc = {
            "id": "general:account:acct-new",
            "entity_type": "account",
            "entity_id": "acct-new",
            "domain": "general",
            "core_record": json.dumps({"name": "New Account", "status": "active"}),
            "related_records": json.dumps([]),
            "recent_events": json.dumps([]),
            "knowledge_hits": json.dumps([]),
            "last_refreshed": "2026-04-26T00:00:00Z",
            "knowledge_refresh_needed": 0,
        }
        await db.upsert_materialized_view(doc)
        result = await db.get_materialized_view("acct-new", "account")
        assert result is not None
        assert result["entity_id"] == "acct-new"

    @pytest.mark.asyncio
    async def test_get_stale_views(self):
        from shared.db_sqlite import SQLiteDB

        db = SQLiteDB(TEST_DB)
        # acct-003 has knowledge_refresh_needed=1 in seed data
        stale = await db.get_stale_views()
        assert any(v["entity_id"] == "acct-003" for v in stale)


# -- Cosmos tests (mocked) -------------------------------------------------


class TestCosmosDB:

    @pytest.mark.asyncio
    async def test_cosmos_get_entity_calls_correct_container(self):
        from shared.db_cosmos import CosmosDB

        with patch("shared.db_cosmos.CosmosClient") as mock_client_cls:
            mock_container = AsyncMock()
            mock_container.read_item = AsyncMock(
                return_value={
                    "id": "general:account:acct-001",
                    "entity_id": "acct-001",
                    "domain": "general",
                    "core_record": "{}",
                }
            )
            mock_db_client = mock_client_cls.return_value.get_database_client.return_value
            mock_db_client.get_container_client.return_value = mock_container

            db = CosmosDB(
                endpoint="https://fake-cosmos-endpoint.example.com",
                database="mcp-db",
            )
            result = await db.get_materialized_view("acct-001", "account")
            assert result["entity_id"] == "acct-001"
            mock_container.read_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_cosmos_get_entity_not_found_returns_none(self):
        from shared.db_cosmos import CosmosDB
        from azure.core.exceptions import ResourceNotFoundError

        with patch("shared.db_cosmos.CosmosClient") as mock_client_cls:
            mock_container = AsyncMock()
            mock_container.read_item = AsyncMock(
                side_effect=ResourceNotFoundError("not found")
            )
            mock_db_client = mock_client_cls.return_value.get_database_client.return_value
            mock_db_client.get_container_client.return_value = mock_container

            db = CosmosDB(
                endpoint="https://fake-cosmos-endpoint.example.com",
                database="mcp-db",
            )
            result = await db.get_materialized_view("missing", "account")
            assert result is None

    @pytest.mark.asyncio
    async def test_cosmos_write_attestation(self):
        from shared.db_cosmos import CosmosDB

        with patch("shared.db_cosmos.CosmosClient") as mock_client_cls:
            mock_container = AsyncMock()
            mock_container.upsert_item = AsyncMock(return_value={})
            mock_db_client = mock_client_cls.return_value.get_database_client.return_value
            mock_db_client.get_container_client.return_value = mock_container

            db = CosmosDB(
                endpoint="https://fake-cosmos-endpoint.example.com",
                database="mcp-db",
            )
            record = {
                "id": "test-001",
                "session_id": "sess-001",
                "tool_name": "get_entity_context",
                "tool_type": "compound",
                "intent": "full_context",
                "domain": "general",
                "entity_id": "acct-001",
                "assembled_sources": "[]",
                "result_hash": "abc",
                "timestamp": "2026-04-26T00:00:00Z",
                "latency_ms": 10,
            }
            await db.write_attestation(record)
            mock_container.upsert_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_cosmos_no_connection_string_in_init(self):
        """Verify CosmosDB init never accepts a connection string."""
        from shared.db_cosmos import CosmosDB

        sig = inspect.signature(CosmosDB.__init__)
        assert "connection_string" not in sig.parameters, (
            "CosmosDB must not accept connection_string — SD-07 violation"
        )
