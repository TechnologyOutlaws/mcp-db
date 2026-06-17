"""
MCP-DB — DB factory.
Returns SQLiteDB or CosmosDB based on DB_VARIANT env var.
Default: sqlite (works offline, no credentials required).

Both variants implement VectorGraphDB (shared/vector_graph.py), so the
returned backend also exposes vector_search / graph_traverse / upsert_node /
upsert_edge in addition to the materialized-view interface.

Usage:
    from shared.db_factory import get_db
    db = get_db()
    result = await db.get_materialized_view("acct-001", "account")
    hits = await db.vector_search([0.1, 0.2, 0.3], top_k=5)
"""

import os


def get_db():
    variant = os.environ.get("DB_VARIANT", "sqlite").lower()
    if variant == "cosmos":
        from shared.db_cosmos import CosmosDB

        return CosmosDB()
    else:
        from shared.db_sqlite import SQLiteDB

        return SQLiteDB()
