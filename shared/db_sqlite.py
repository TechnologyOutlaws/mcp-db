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

import json
import math
import aiosqlite
from pathlib import Path

from shared.vector_graph import VectorGraphDB

DEFAULT_DB_PATH = Path(__file__).parent.parent / "mcp_db.sqlite"


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Pure-Python cosine similarity. Returns 0.0 for degenerate inputs."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


class SQLiteDB(VectorGraphDB):

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

    # ── Vector-Graph methods (VectorGraphDB) ──────────────────────────
    #
    # Pure-Python approach: embeddings stored as JSON in graph_node.embedding,
    # vector_search loads candidate rows and ranks by cosine similarity in
    # process. No native extension (sqlite-vec is not a dependency, and the
    # SQLite variant must run offline with no extra deps). graph_traverse is
    # BFS over the graph_edge table to the requested depth.

    async def upsert_node(
        self,
        node_id: str,
        node_type: str,
        properties: dict,
        embedding: list[float],
    ) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT OR REPLACE INTO graph_node
                   (node_id, node_type, properties, embedding)
                   VALUES (?, ?, ?, ?)""",
                (
                    node_id,
                    node_type,
                    json.dumps(properties or {}),
                    json.dumps(embedding or []),
                ),
            )
            await db.commit()

    async def upsert_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str,
        weight: float = 1.0,
    ) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT OR REPLACE INTO graph_edge
                   (source_id, target_id, edge_type, weight)
                   VALUES (?, ?, ?, ?)""",
                (source_id, target_id, edge_type, weight),
            )
            await db.commit()

    async def vector_search(
        self,
        query_vector: list[float],
        top_k: int = 5,
        filters: dict | None = None,
    ) -> list[dict]:
        filters = filters or {}
        sql = "SELECT node_id, node_type, properties, embedding FROM graph_node"
        params: list = []
        if "node_type" in filters:
            sql += " WHERE node_type = ?"
            params.append(filters["node_type"])

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(sql, params)
            rows = await cur.fetchall()

        scored = []
        for row in rows:
            embedding = json.loads(row["embedding"]) if row["embedding"] else []
            score = _cosine_similarity(query_vector, embedding)
            scored.append(
                {
                    "node_id": row["node_id"],
                    "node_type": row["node_type"],
                    "properties": row["properties"],
                    "score": score,
                }
            )
        scored.sort(key=lambda r: r["score"], reverse=True)
        return scored[:top_k]

    async def graph_traverse(
        self,
        start_node_id: str,
        depth: int = 1,
        edge_types: list[str] | None = None,
    ) -> dict:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            # Confirm the start node exists; if not, empty result.
            cur = await db.execute(
                "SELECT node_id FROM graph_node WHERE node_id = ?",
                (start_node_id,),
            )
            if await cur.fetchone() is None:
                return {"nodes": [], "edges": []}

            visited = {start_node_id}
            frontier = [start_node_id]
            reached_edges: list[dict] = []

            for _ in range(max(0, depth)):
                if not frontier:
                    break
                placeholders = ",".join("?" for _ in frontier)
                sql = (
                    "SELECT source_id, target_id, edge_type, weight "
                    f"FROM graph_edge WHERE source_id IN ({placeholders})"
                )
                params = list(frontier)
                if edge_types:
                    et_ph = ",".join("?" for _ in edge_types)
                    sql += f" AND edge_type IN ({et_ph})"
                    params.extend(edge_types)

                cur = await db.execute(sql, params)
                edge_rows = await cur.fetchall()

                next_frontier = []
                for er in edge_rows:
                    reached_edges.append(
                        {
                            "source_id": er["source_id"],
                            "target_id": er["target_id"],
                            "edge_type": er["edge_type"],
                            "weight": er["weight"],
                        }
                    )
                    tgt = er["target_id"]
                    if tgt not in visited:
                        visited.add(tgt)
                        next_frontier.append(tgt)
                frontier = next_frontier

            reached_ids = [nid for nid in visited if nid != start_node_id]
            nodes: list[dict] = []
            if reached_ids:
                placeholders = ",".join("?" for _ in reached_ids)
                cur = await db.execute(
                    "SELECT node_id, node_type, properties, embedding "
                    f"FROM graph_node WHERE node_id IN ({placeholders})",
                    reached_ids,
                )
                node_rows = await cur.fetchall()
                nodes = [
                    {
                        "node_id": r["node_id"],
                        "node_type": r["node_type"],
                        "properties": r["properties"],
                    }
                    for r in node_rows
                ]

            return {"nodes": nodes, "edges": reached_edges}
