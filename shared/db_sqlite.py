"""
MCP-DB — SQLite DB abstraction layer.
Zero cloud dependencies. Runs fully offline.
All methods async via aiosqlite.

Interface (same signatures as db_cosmos.py):
  get_materialized_view(entity_id, entity_type) -> dict | None
  get_route(domain, intent) -> dict | None
  search_knowledge(query, top, tier_min) -> list[dict]
  write_attestation(record) -> None
  get_attestation(record_id) -> dict | None
  upsert_materialized_view(doc) -> None
  get_stale_views() -> list[dict]
"""

import aiosqlite
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).parent.parent / "mcp_db.sqlite"


class SQLiteDB:

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH):
        self.db_path = str(db_path)

    async def get_materialized_view(
        self, entity_id: str, entity_type: str
    ) -> dict | None:
        view_id = f"general:{entity_type}:{entity_id}"
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM materialized_intelligence_view WHERE id = ?",
                (view_id,),
            )
            row = await cur.fetchone()
            return dict(row) if row else None

    async def get_route(self, domain: str, intent: str) -> dict | None:
        route_id = f"{domain}:{intent}"
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM intent_routing_table WHERE id = ?",
                (route_id,),
            )
            row = await cur.fetchone()
            return dict(row) if row else None

    async def search_knowledge(
        self, query: str, top: int = 5, tier_min: int = 1
    ) -> list[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """SELECT kb.id, kb.domain, kb.content, kb.citation,
                          kb.confidence, kb.source_tier, kb.last_verified
                   FROM knowledge_fts
                   JOIN knowledge_base kb ON knowledge_fts.id = kb.id
                   WHERE knowledge_fts MATCH ?
                     AND kb.source_tier >= ?
                   LIMIT ?""",
                (query, tier_min, top),
            )
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def write_attestation(self, record: dict) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT OR REPLACE INTO compound_attestation_log
                   (id, session_id, tool_name, tool_type, intent, domain,
                    entity_id, assembled_sources, result_hash, timestamp,
                    latency_ms)
                   VALUES (:id, :session_id, :tool_name, :tool_type, :intent,
                           :domain, :entity_id, :assembled_sources,
                           :result_hash, :timestamp, :latency_ms)""",
                record,
            )
            await db.commit()

    async def get_attestation(self, record_id: str) -> dict | None:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM compound_attestation_log WHERE id = ?",
                (record_id,),
            )
            row = await cur.fetchone()
            return dict(row) if row else None

    async def upsert_materialized_view(self, doc: dict) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT OR REPLACE INTO materialized_intelligence_view
                   (id, entity_type, entity_id, domain, core_record,
                    related_records, recent_events, knowledge_hits,
                    last_refreshed, knowledge_refresh_needed)
                   VALUES (:id, :entity_type, :entity_id, :domain,
                           :core_record, :related_records, :recent_events,
                           :knowledge_hits, :last_refreshed,
                           :knowledge_refresh_needed)""",
                doc,
            )
            await db.commit()

    async def get_stale_views(self) -> list[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """SELECT * FROM materialized_intelligence_view
                   WHERE knowledge_refresh_needed = 1"""
            )
            rows = await cur.fetchall()
            return [dict(r) for r in rows]
