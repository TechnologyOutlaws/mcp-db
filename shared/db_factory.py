"""
MCP-DB — DB factory.
Returns SQLiteDB or CosmosDB based on DB_VARIANT env var.
Default: sqlite (works offline, no credentials required).

Usage:
    from shared.db_factory import get_db
    db = get_db()
    result = await db.get_materialized_view("acct-001", "account")
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
