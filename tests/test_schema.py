import pytest
import asyncio
import aiosqlite
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

DB_PATH = "test_mcp_db.sqlite"


@pytest.fixture(autouse=True)
async def clean_db():
    """Remove test DB before and after each test."""
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    yield
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)


async def get_table_names(db_path: str) -> list[str]:
    async with aiosqlite.connect(db_path) as db:
        cur = await db.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','view') "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
        rows = await cur.fetchall()
        return [r[0] for r in rows]


async def get_column_names(db_path: str, table: str) -> list[str]:
    async with aiosqlite.connect(db_path) as db:
        cur = await db.execute(f"PRAGMA table_info({table})")
        rows = await cur.fetchall()
        return [r[1] for r in rows]


# ── Table existence ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_init_creates_all_tables():
    from scripts.init_db import init_database

    await init_database(DB_PATH)
    tables = await get_table_names(DB_PATH)
    expected = [
        "compound_attestation_log",
        "intent_routing_table",
        "knowledge_base",
        "knowledge_fts",
        "knowledge_fts_config",
        "knowledge_fts_content",
        "knowledge_fts_data",
        "knowledge_fts_docsize",
        "knowledge_fts_idx",
        "materialized_intelligence_view",
    ]
    for t in ["compound_attestation_log", "intent_routing_table",
              "knowledge_base", "knowledge_fts",
              "materialized_intelligence_view"]:
        assert t in tables, f"Missing table: {t}"


# ── Schema checks ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_materialized_view_schema():
    from scripts.init_db import init_database

    await init_database(DB_PATH)
    cols = await get_column_names(DB_PATH, "materialized_intelligence_view")
    for col in ["id", "entity_type", "entity_id", "domain", "core_record",
                "related_records", "recent_events", "knowledge_hits",
                "last_refreshed", "knowledge_refresh_needed"]:
        assert col in cols, f"Missing column: {col}"


@pytest.mark.asyncio
async def test_intent_routing_table_schema():
    from scripts.init_db import init_database

    await init_database(DB_PATH)
    cols = await get_column_names(DB_PATH, "intent_routing_table")
    for col in ["id", "domain", "intent", "query_strategy",
                "required_params", "optional_params", "defaults_json",
                "vector_search_filter", "cache_ttl_seconds"]:
        assert col in cols, f"Missing column: {col}"


@pytest.mark.asyncio
async def test_compound_attestation_log_schema():
    from scripts.init_db import init_database

    await init_database(DB_PATH)
    cols = await get_column_names(DB_PATH, "compound_attestation_log")
    for col in ["id", "session_id", "tool_name", "tool_type", "intent",
                "domain", "entity_id", "assembled_sources", "result_hash",
                "timestamp", "latency_ms"]:
        assert col in cols, f"Missing column: {col}"


@pytest.mark.asyncio
async def test_knowledge_base_schema():
    from scripts.init_db import init_database

    await init_database(DB_PATH)
    cols = await get_column_names(DB_PATH, "knowledge_base")
    for col in ["id", "domain", "content", "citation",
                "confidence", "source_tier", "last_verified"]:
        assert col in cols, f"Missing column: {col}"


@pytest.mark.asyncio
async def test_fts5_table_exists():
    from scripts.init_db import init_database

    await init_database(DB_PATH)
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='knowledge_fts'"
        )
        rows = await cur.fetchall()
        assert len(rows) == 1


# ── Idempotency ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_idempotent_init():
    from scripts.init_db import init_database

    await init_database(DB_PATH)
    await init_database(DB_PATH)
    tables = await get_table_names(DB_PATH)
    core = [t for t in tables if t in [
        "compound_attestation_log", "intent_routing_table",
        "knowledge_base", "knowledge_fts",
        "materialized_intelligence_view"
    ]]
    assert len(core) == 5


# ── Seed tests ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_seed_loads_routes():
    from scripts.init_db import init_database
    from scripts.seed import seed_database

    await init_database(DB_PATH)
    await seed_database(DB_PATH)
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM intent_routing_table")
        row = await cur.fetchone()
        assert row[0] == 4


@pytest.mark.asyncio
async def test_seed_loads_entities():
    from scripts.init_db import init_database
    from scripts.seed import seed_database

    await init_database(DB_PATH)
    await seed_database(DB_PATH)
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT COUNT(*) FROM materialized_intelligence_view"
        )
        row = await cur.fetchone()
        assert row[0] == 3


@pytest.mark.asyncio
async def test_seed_loads_knowledge():
    from scripts.init_db import init_database
    from scripts.seed import seed_database

    await init_database(DB_PATH)
    await seed_database(DB_PATH)
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM knowledge_base")
        row = await cur.fetchone()
        assert row[0] == 10


@pytest.mark.asyncio
async def test_fts5_search_works():
    from scripts.init_db import init_database
    from scripts.seed import seed_database

    await init_database(DB_PATH)
    await seed_database(DB_PATH)
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT id FROM knowledge_fts WHERE knowledge_fts MATCH 'contract'"
        )
        rows = await cur.fetchall()
        assert len(rows) >= 1


@pytest.mark.asyncio
async def test_seed_is_idempotent():
    from scripts.init_db import init_database
    from scripts.seed import seed_database

    await init_database(DB_PATH)
    await seed_database(DB_PATH)
    await seed_database(DB_PATH)
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM intent_routing_table")
        assert (await cur.fetchone())[0] == 4
        cur = await db.execute(
            "SELECT COUNT(*) FROM materialized_intelligence_view"
        )
        assert (await cur.fetchone())[0] == 3
        cur = await db.execute("SELECT COUNT(*) FROM knowledge_base")
        assert (await cur.fetchone())[0] == 10
