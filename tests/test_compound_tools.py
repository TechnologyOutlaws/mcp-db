import pytest
import pytest_asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

TEST_DB = "test_compound.sqlite"


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    from scripts.init_db import init_database
    from scripts.seed import seed_database

    await init_database(TEST_DB)
    await seed_database(TEST_DB)
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


# -- get_entity_context ----------------------------------------------------


class TestGetEntityContext:

    @pytest.mark.asyncio
    async def test_returns_assembled_result(self):
        from shared.tools.compound.get_entity_context import get_entity_context
        from shared.db_sqlite import SQLiteDB

        db = SQLiteDB(TEST_DB)
        result = await get_entity_context(
            entity_id="acct-001",
            entity_type="account",
            intent="full_context",
            domain="general",
            db=db,
        )
        assert result is not None
        assert "entity" in result
        assert "records" in result
        assert "events" in result
        assert "knowledge_hits" in result
        assert "assembled_sources" in result
        assert "attestation_record_id" in result

    @pytest.mark.asyncio
    async def test_one_attestation_record_written(self):
        from shared.tools.compound.get_entity_context import get_entity_context
        from shared.db_sqlite import SQLiteDB

        db = SQLiteDB(TEST_DB)
        result = await get_entity_context(
            entity_id="acct-001",
            entity_type="account",
            intent="full_context",
            domain="general",
            db=db,
        )
        record = await db.get_attestation(result["attestation_record_id"])
        assert record is not None
        assert record["tool_name"] == "get_entity_context"
        assert record["tool_type"] == "compound"

    @pytest.mark.asyncio
    async def test_assembled_sources_not_empty(self):
        from shared.tools.compound.get_entity_context import get_entity_context
        from shared.db_sqlite import SQLiteDB

        db = SQLiteDB(TEST_DB)
        result = await get_entity_context(
            entity_id="acct-001",
            entity_type="account",
            intent="full_context",
            domain="general",
            db=db,
        )
        assert len(result["assembled_sources"]) >= 1
        assert any("materialized_view" in s for s in result["assembled_sources"])

    @pytest.mark.asyncio
    async def test_unknown_entity_returns_none(self):
        from shared.tools.compound.get_entity_context import get_entity_context
        from shared.db_sqlite import SQLiteDB

        db = SQLiteDB(TEST_DB)
        result = await get_entity_context(
            entity_id="does-not-exist",
            entity_type="account",
            intent="full_context",
            domain="general",
            db=db,
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_unknown_intent_returns_none(self):
        from shared.tools.compound.get_entity_context import get_entity_context
        from shared.db_sqlite import SQLiteDB

        db = SQLiteDB(TEST_DB)
        result = await get_entity_context(
            entity_id="acct-001",
            entity_type="account",
            intent="nonexistent_intent",
            domain="general",
            db=db,
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_include_knowledge_false_skips_fts(self):
        from shared.tools.compound.get_entity_context import get_entity_context
        from shared.db_sqlite import SQLiteDB

        db = SQLiteDB(TEST_DB)
        result = await get_entity_context(
            entity_id="acct-001",
            entity_type="account",
            intent="full_context",
            domain="general",
            include_knowledge=False,
            db=db,
        )
        assert result is not None
        assert result["knowledge_hits"] == []

    @pytest.mark.asyncio
    async def test_attestation_contains_assembled_sources(self):
        from shared.tools.compound.get_entity_context import get_entity_context
        from shared.db_sqlite import SQLiteDB

        db = SQLiteDB(TEST_DB)
        result = await get_entity_context(
            entity_id="acct-001",
            entity_type="account",
            intent="full_context",
            domain="general",
            db=db,
        )
        record = await db.get_attestation(result["attestation_record_id"])
        sources = json.loads(record["assembled_sources"])
        assert isinstance(sources, list)
        assert len(sources) >= 1


# -- search_knowledge ------------------------------------------------------


class TestSearchKnowledge:

    @pytest.mark.asyncio
    async def test_returns_hits(self):
        from shared.tools.compound.search_knowledge import search_knowledge
        from shared.db_sqlite import SQLiteDB

        db = SQLiteDB(TEST_DB)
        result = await search_knowledge(query="contract", db=db)
        assert result is not None
        assert "hits" in result
        assert len(result["hits"]) >= 1

    @pytest.mark.asyncio
    async def test_returns_attestation_record_id(self):
        from shared.tools.compound.search_knowledge import search_knowledge
        from shared.db_sqlite import SQLiteDB

        db = SQLiteDB(TEST_DB)
        result = await search_knowledge(query="contract", db=db)
        assert "attestation_record_id" in result
        record = await db.get_attestation(result["attestation_record_id"])
        assert record["tool_name"] == "search_knowledge"
        assert record["tool_type"] == "compound"

    @pytest.mark.asyncio
    async def test_top_param_respected(self):
        from shared.tools.compound.search_knowledge import search_knowledge
        from shared.db_sqlite import SQLiteDB

        db = SQLiteDB(TEST_DB)
        result = await search_knowledge(query="account", top=2, db=db)
        assert len(result["hits"]) <= 2

    @pytest.mark.asyncio
    async def test_no_results_returns_empty_hits(self):
        from shared.tools.compound.search_knowledge import search_knowledge
        from shared.db_sqlite import SQLiteDB

        db = SQLiteDB(TEST_DB)
        result = await search_knowledge(query="zzznomatchzzz", db=db)
        assert result["hits"] == []
        assert "attestation_record_id" in result

    @pytest.mark.asyncio
    async def test_assembled_sources_from_fts_hits(self):
        from shared.tools.compound.search_knowledge import search_knowledge
        from shared.db_sqlite import SQLiteDB

        db = SQLiteDB(TEST_DB)
        result = await search_knowledge(query="contract", db=db)
        assert any("fts::" in s for s in result["assembled_sources"])
