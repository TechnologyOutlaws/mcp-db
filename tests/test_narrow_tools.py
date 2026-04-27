import pytest
import pytest_asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

TEST_DB = "test_narrow.sqlite"


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    from scripts.init_db import init_database
    from scripts.seed import seed_database

    await init_database(TEST_DB)
    await seed_database(TEST_DB)
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


# -- get_entity ------------------------------------------------------------


class TestGetEntity:

    @pytest.mark.asyncio
    async def test_returns_core_record(self):
        from shared.tools.narrow.get_entity import get_entity
        from shared.db_sqlite import SQLiteDB

        db = SQLiteDB(TEST_DB)
        result = await get_entity(entity_id="acct-001", entity_type="account", db=db)
        assert result is not None
        assert "entity" in result
        assert result["entity"]["status"] == "active"

    @pytest.mark.asyncio
    async def test_returns_attestation_record_id(self):
        from shared.tools.narrow.get_entity import get_entity
        from shared.db_sqlite import SQLiteDB

        db = SQLiteDB(TEST_DB)
        result = await get_entity("acct-001", "account", db=db)
        assert "attestation_record_id" in result
        assert isinstance(result["attestation_record_id"], str)
        assert len(result["attestation_record_id"]) == 36

    @pytest.mark.asyncio
    async def test_not_found_returns_none(self):
        from shared.tools.narrow.get_entity import get_entity
        from shared.db_sqlite import SQLiteDB

        db = SQLiteDB(TEST_DB)
        result = await get_entity("does-not-exist", "account", db=db)
        assert result is None

    @pytest.mark.asyncio
    async def test_attestation_written_to_db(self):
        from shared.tools.narrow.get_entity import get_entity
        from shared.db_sqlite import SQLiteDB

        db = SQLiteDB(TEST_DB)
        result = await get_entity("acct-001", "account", db=db)
        record = await db.get_attestation(result["attestation_record_id"])
        assert record is not None
        assert record["tool_name"] == "get_entity"
        assert record["tool_type"] == "narrow"


# -- get_records -----------------------------------------------------------


class TestGetRecords:

    @pytest.mark.asyncio
    async def test_returns_records_list(self):
        from shared.tools.narrow.get_records import get_records
        from shared.db_sqlite import SQLiteDB

        db = SQLiteDB(TEST_DB)
        result = await get_records("acct-001", "account", db=db)
        assert result is not None
        assert "records" in result
        assert isinstance(result["records"], list)
        assert len(result["records"]) >= 1

    @pytest.mark.asyncio
    async def test_entity_with_no_records_returns_empty_list(self):
        from shared.tools.narrow.get_records import get_records
        from shared.db_sqlite import SQLiteDB

        db = SQLiteDB(TEST_DB)
        result = await get_records("acct-003", "account", db=db)
        assert result is not None
        assert result["records"] == []

    @pytest.mark.asyncio
    async def test_returns_attestation_record_id(self):
        from shared.tools.narrow.get_records import get_records
        from shared.db_sqlite import SQLiteDB

        db = SQLiteDB(TEST_DB)
        result = await get_records("acct-001", "account", db=db)
        assert "attestation_record_id" in result

    @pytest.mark.asyncio
    async def test_attestation_tool_name(self):
        from shared.tools.narrow.get_records import get_records
        from shared.db_sqlite import SQLiteDB

        db = SQLiteDB(TEST_DB)
        result = await get_records("acct-001", "account", db=db)
        record = await db.get_attestation(result["attestation_record_id"])
        assert record["tool_name"] == "get_records"
        assert record["tool_type"] == "narrow"


# -- get_recent_events -----------------------------------------------------


class TestGetRecentEvents:

    @pytest.mark.asyncio
    async def test_returns_events_list(self):
        from shared.tools.narrow.get_recent_events import get_recent_events
        from shared.db_sqlite import SQLiteDB

        db = SQLiteDB(TEST_DB)
        result = await get_recent_events("acct-001", "account", db=db)
        assert result is not None
        assert "events" in result
        assert isinstance(result["events"], list)
        assert len(result["events"]) >= 1

    @pytest.mark.asyncio
    async def test_limit_param_respected(self):
        from shared.tools.narrow.get_recent_events import get_recent_events
        from shared.db_sqlite import SQLiteDB

        db = SQLiteDB(TEST_DB)
        result = await get_recent_events("acct-001", "account", db=db, limit=1)
        assert len(result["events"]) <= 1

    @pytest.mark.asyncio
    async def test_returns_attestation_record_id(self):
        from shared.tools.narrow.get_recent_events import get_recent_events
        from shared.db_sqlite import SQLiteDB

        db = SQLiteDB(TEST_DB)
        result = await get_recent_events("acct-001", "account", db=db)
        assert "attestation_record_id" in result

    @pytest.mark.asyncio
    async def test_attestation_tool_name(self):
        from shared.tools.narrow.get_recent_events import get_recent_events
        from shared.db_sqlite import SQLiteDB

        db = SQLiteDB(TEST_DB)
        result = await get_recent_events("acct-001", "account", db=db)
        record = await db.get_attestation(result["attestation_record_id"])
        assert record["tool_name"] == "get_recent_events"
        assert record["tool_type"] == "narrow"


# -- get_knowledge_hits ----------------------------------------------------


class TestGetKnowledgeHits:

    @pytest.mark.asyncio
    async def test_returns_hits_list(self):
        from shared.tools.narrow.get_knowledge_hits import get_knowledge_hits
        from shared.db_sqlite import SQLiteDB

        db = SQLiteDB(TEST_DB)
        result = await get_knowledge_hits(query="contract", db=db)
        assert result is not None
        assert "hits" in result
        assert isinstance(result["hits"], list)
        assert len(result["hits"]) >= 1

    @pytest.mark.asyncio
    async def test_top_param_respected(self):
        from shared.tools.narrow.get_knowledge_hits import get_knowledge_hits
        from shared.db_sqlite import SQLiteDB

        db = SQLiteDB(TEST_DB)
        result = await get_knowledge_hits("account", db=db, top=2)
        assert len(result["hits"]) <= 2

    @pytest.mark.asyncio
    async def test_no_results_returns_empty_list(self):
        from shared.tools.narrow.get_knowledge_hits import get_knowledge_hits
        from shared.db_sqlite import SQLiteDB

        db = SQLiteDB(TEST_DB)
        result = await get_knowledge_hits("zzznomatchzzz", db=db)
        assert result["hits"] == []

    @pytest.mark.asyncio
    async def test_returns_attestation_record_id(self):
        from shared.tools.narrow.get_knowledge_hits import get_knowledge_hits
        from shared.db_sqlite import SQLiteDB

        db = SQLiteDB(TEST_DB)
        result = await get_knowledge_hits("contract", db=db)
        assert "attestation_record_id" in result

    @pytest.mark.asyncio
    async def test_attestation_tool_name(self):
        from shared.tools.narrow.get_knowledge_hits import get_knowledge_hits
        from shared.db_sqlite import SQLiteDB

        db = SQLiteDB(TEST_DB)
        result = await get_knowledge_hits("contract", db=db)
        record = await db.get_attestation(result["attestation_record_id"])
        assert record["tool_name"] == "get_knowledge_hits"
        assert record["tool_type"] == "narrow"
