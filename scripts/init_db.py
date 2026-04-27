"""
MCP-DB — SQLite schema initialization.
Run once to create all tables. Safe to re-run (IF NOT EXISTS).
Usage: python scripts/init_db.py [db_path]
Default db_path: mcp_db.sqlite in repo root.
"""

import asyncio
import aiosqlite
import sys
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).parent.parent / "mcp_db.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS materialized_intelligence_view (
    id                       TEXT PRIMARY KEY,
    entity_type              TEXT NOT NULL,
    entity_id                TEXT NOT NULL,
    domain                   TEXT NOT NULL,
    core_record              TEXT NOT NULL DEFAULT '{}',
    related_records          TEXT NOT NULL DEFAULT '[]',
    recent_events            TEXT NOT NULL DEFAULT '[]',
    knowledge_hits           TEXT NOT NULL DEFAULT '[]',
    last_refreshed           TEXT NOT NULL,
    knowledge_refresh_needed INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS intent_routing_table (
    id                   TEXT PRIMARY KEY,
    domain               TEXT NOT NULL,
    intent               TEXT NOT NULL,
    query_strategy       TEXT NOT NULL,
    required_params      TEXT NOT NULL DEFAULT '[]',
    optional_params      TEXT NOT NULL DEFAULT '[]',
    defaults_json        TEXT NOT NULL DEFAULT '{}',
    vector_search_filter TEXT,
    cache_ttl_seconds    INTEGER NOT NULL DEFAULT 300
);

CREATE TABLE IF NOT EXISTS compound_attestation_log (
    id                TEXT PRIMARY KEY,
    session_id        TEXT NOT NULL,
    tool_name         TEXT NOT NULL,
    tool_type         TEXT NOT NULL DEFAULT 'compound',
    intent            TEXT,
    domain            TEXT,
    entity_id         TEXT,
    assembled_sources TEXT NOT NULL DEFAULT '[]',
    result_hash       TEXT NOT NULL,
    timestamp         TEXT NOT NULL,
    latency_ms        INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS knowledge_base (
    id            TEXT PRIMARY KEY,
    domain        TEXT NOT NULL,
    content       TEXT NOT NULL,
    citation      TEXT NOT NULL,
    confidence    TEXT NOT NULL DEFAULT 'MEDIUM',
    source_tier   INTEGER NOT NULL DEFAULT 2,
    last_verified TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts
    USING fts5(id, domain, content, citation,
               content='knowledge_base', content_rowid='rowid');
"""

TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS knowledge_base_ai
    AFTER INSERT ON knowledge_base BEGIN
        INSERT INTO knowledge_fts(rowid, id, domain, content, citation)
        VALUES (new.rowid, new.id, new.domain, new.content, new.citation);
    END;

CREATE TRIGGER IF NOT EXISTS knowledge_base_ad
    AFTER DELETE ON knowledge_base BEGIN
        INSERT INTO knowledge_fts(knowledge_fts, rowid, id, domain, content, citation)
        VALUES ('delete', old.rowid, old.id, old.domain, old.content, old.citation);
    END;

CREATE TRIGGER IF NOT EXISTS knowledge_base_au
    AFTER UPDATE ON knowledge_base BEGIN
        INSERT INTO knowledge_fts(knowledge_fts, rowid, id, domain, content, citation)
        VALUES ('delete', old.rowid, old.id, old.domain, old.content, old.citation);
        INSERT INTO knowledge_fts(rowid, id, domain, content, citation)
        VALUES (new.rowid, new.id, new.domain, new.content, new.citation);
    END;
"""


async def init_database(db_path: str | Path = DEFAULT_DB_PATH) -> None:
    """Create all tables and FTS triggers. Safe to re-run."""
    async with aiosqlite.connect(str(db_path)) as db:
        await db.executescript(SCHEMA)
        await db.executescript(TRIGGERS)
        await db.commit()
    print(f"Schema initialized: {db_path}")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DB_PATH
    asyncio.run(init_database(path))
