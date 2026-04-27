"""
MCP-DB — Seed data for local development and testing.
Loads:
  - 4 intent routes into intent_routing_table
  - 3 example entities into materialized_intelligence_view
  - 10 example knowledge documents into knowledge_base (+ FTS index)
Safe to re-run (INSERT OR REPLACE).
Usage: python scripts/seed.py [db_path]
"""

import asyncio
import aiosqlite
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).parent.parent / "mcp_db.sqlite"
NOW = datetime.now(timezone.utc).isoformat()

# -- Intent Routes --------------------------------------------------------

ROUTES = [
    {
        "id": "general:full_context",
        "domain": "general",
        "intent": "full_context",
        "query_strategy": "materialized_view",
        "required_params": json.dumps(["entity_id"]),
        "optional_params": json.dumps(["include_events", "include_knowledge",
                                        "knowledge_limit"]),
        "defaults_json": json.dumps({
            "include_events": True,
            "include_knowledge": True,
            "knowledge_limit": 5
        }),
        "vector_search_filter": None,
        "cache_ttl_seconds": 300
    },
    {
        "id": "general:summary",
        "domain": "general",
        "intent": "summary",
        "query_strategy": "materialized_view",
        "required_params": json.dumps(["entity_id"]),
        "optional_params": json.dumps(["include_knowledge"]),
        "defaults_json": json.dumps({
            "include_events": False,
            "include_knowledge": True,
            "knowledge_limit": 3
        }),
        "vector_search_filter": None,
        "cache_ttl_seconds": 600
    },
    {
        "id": "general:audit_context",
        "domain": "general",
        "intent": "audit_context",
        "query_strategy": "materialized_view",
        "required_params": json.dumps(["entity_id"]),
        "optional_params": json.dumps([]),
        "defaults_json": json.dumps({
            "include_events": True,
            "include_knowledge": False,
            "knowledge_limit": 0
        }),
        "vector_search_filter": None,
        "cache_ttl_seconds": 60
    },
    {
        "id": "general:knowledge_search",
        "domain": "general",
        "intent": "knowledge_search",
        "query_strategy": "fts_only",
        "required_params": json.dumps(["query"]),
        "optional_params": json.dumps(["domain", "top", "tier_min"]),
        "defaults_json": json.dumps({
            "top": 5,
            "tier_min": 1
        }),
        "vector_search_filter": None,
        "cache_ttl_seconds": 300
    },
]

# -- Example Entities ------------------------------------------------------

ENTITIES = [
    {
        "id": "general:account:acct-001",
        "entity_type": "account",
        "entity_id": "acct-001",
        "domain": "general",
        "core_record": json.dumps({
            "name": "Example Account Alpha",
            "status": "active",
            "created_date": "2025-01-15",
            "account_type": "standard"
        }),
        "related_records": json.dumps([
            {"record_id": "rec-001", "type": "contract", "status": "active",
             "created_date": "2025-02-01"},
            {"record_id": "rec-002", "type": "agreement", "status": "pending",
             "created_date": "2025-03-10"}
        ]),
        "recent_events": json.dumps([
            {"date": "2026-04-20", "event": "Status updated to active",
             "source": "system"},
            {"date": "2026-04-15", "event": "New record rec-002 created",
             "source": "user"},
            {"date": "2026-04-01", "event": "Annual review completed",
             "source": "system"}
        ]),
        "knowledge_hits": json.dumps([
            {"citation": "Standard Account Protocol \u00a7 2.1",
             "confidence": "HIGH", "source_tier": 1},
            {"citation": "Account Management Guide \u00a7 5.3",
             "confidence": "MEDIUM", "source_tier": 2}
        ]),
        "last_refreshed": NOW,
        "knowledge_refresh_needed": 0
    },
    {
        "id": "general:account:acct-002",
        "entity_type": "account",
        "entity_id": "acct-002",
        "domain": "general",
        "core_record": json.dumps({
            "name": "Example Account Beta",
            "status": "review",
            "created_date": "2025-06-01",
            "account_type": "premium"
        }),
        "related_records": json.dumps([
            {"record_id": "rec-003", "type": "contract", "status": "active",
             "created_date": "2025-06-15"}
        ]),
        "recent_events": json.dumps([
            {"date": "2026-04-22", "event": "Placed under review",
             "source": "system"},
            {"date": "2026-04-10", "event": "Compliance check initiated",
             "source": "user"}
        ]),
        "knowledge_hits": json.dumps([
            {"citation": "Review Procedures \u00a7 1.4",
             "confidence": "HIGH", "source_tier": 1}
        ]),
        "last_refreshed": NOW,
        "knowledge_refresh_needed": 0
    },
    {
        "id": "general:account:acct-003",
        "entity_type": "account",
        "entity_id": "acct-003",
        "domain": "general",
        "core_record": json.dumps({
            "name": "Example Account Gamma",
            "status": "inactive",
            "created_date": "2024-11-01",
            "account_type": "standard"
        }),
        "related_records": json.dumps([]),
        "recent_events": json.dumps([
            {"date": "2026-01-15", "event": "Account deactivated",
             "source": "system"}
        ]),
        "knowledge_hits": json.dumps([]),
        "last_refreshed": NOW,
        "knowledge_refresh_needed": 1
    },
]

# -- Knowledge Documents ---------------------------------------------------

KNOWLEDGE_DOCS = [
    {
        "id": "kb-001",
        "domain": "general",
        "content": "Standard account activation requires identity verification "
                   "and agreement to terms of service before the account "
                   "becomes active in the system.",
        "citation": "Account Activation Protocol \u00a7 1.1",
        "confidence": "HIGH",
        "source_tier": 1,
        "last_verified": "2026-04-01"
    },
    {
        "id": "kb-002",
        "domain": "general",
        "content": "Contract review procedures require a minimum of two "
                   "authorized reviewers before a contract can be executed. "
                   "All contracts must include an expiration date.",
        "citation": "Contract Management Guidelines \u00a7 3.2",
        "confidence": "HIGH",
        "source_tier": 1,
        "last_verified": "2026-04-01"
    },
    {
        "id": "kb-003",
        "domain": "general",
        "content": "Accounts placed under review status are restricted from "
                   "initiating new contracts until the review is resolved. "
                   "Review resolution requires written authorization.",
        "citation": "Review Procedures \u00a7 1.4",
        "confidence": "HIGH",
        "source_tier": 1,
        "last_verified": "2026-03-15"
    },
    {
        "id": "kb-004",
        "domain": "general",
        "content": "Inactive accounts retain their records for a minimum of "
                   "seven years in accordance with standard retention policy. "
                   "Records cannot be deleted during the retention period.",
        "citation": "Data Retention Policy \u00a7 2.0",
        "confidence": "HIGH",
        "source_tier": 1,
        "last_verified": "2026-03-01"
    },
    {
        "id": "kb-005",
        "domain": "general",
        "content": "Premium accounts are subject to enhanced compliance checks "
                   "on a quarterly basis. Compliance check results must be "
                   "documented and retained.",
        "citation": "Account Management Guide \u00a7 5.3",
        "confidence": "MEDIUM",
        "source_tier": 2,
        "last_verified": "2026-02-15"
    },
    {
        "id": "kb-006",
        "domain": "general",
        "content": "An agreement in pending status must be resolved within "
                   "thirty days of creation. Agreements not resolved within "
                   "thirty days are automatically cancelled.",
        "citation": "Agreement Lifecycle Policy \u00a7 4.1",
        "confidence": "HIGH",
        "source_tier": 1,
        "last_verified": "2026-04-10"
    },
    {
        "id": "kb-007",
        "domain": "general",
        "content": "Audit context requests must capture a complete event "
                   "history for the entity. The audit trail must be "
                   "tamper-evident and include timestamps for all events.",
        "citation": "Audit Requirements \u00a7 7.2",
        "confidence": "HIGH",
        "source_tier": 1,
        "last_verified": "2026-04-05"
    },
    {
        "id": "kb-008",
        "domain": "general",
        "content": "Knowledge refresh is triggered automatically when source "
                   "documents are updated. Stale knowledge is flagged after "
                   "twenty-four hours and refreshed in the next scheduled run.",
        "citation": "Knowledge Management Protocol \u00a7 3.1",
        "confidence": "MEDIUM",
        "source_tier": 2,
        "last_verified": "2026-03-20"
    },
    {
        "id": "kb-009",
        "domain": "general",
        "content": "Standard account protocol requires that all status changes "
                   "be recorded as events with the originating user or system "
                   "identified as the source.",
        "citation": "Standard Account Protocol \u00a7 2.1",
        "confidence": "HIGH",
        "source_tier": 1,
        "last_verified": "2026-04-01"
    },
    {
        "id": "kb-010",
        "domain": "general",
        "content": "Compound tool calls produce a single attestation record "
                   "containing the full source manifest of all data contributing "
                   "to the assembled result. This record is the authoritative "
                   "provenance for the response.",
        "citation": "Compound Query Tier Specification \u00a7 3.5.6",
        "confidence": "HIGH",
        "source_tier": 1,
        "last_verified": "2026-04-26"
    },
]

# -- Seed Function ---------------------------------------------------------


async def seed_database(db_path: str | Path = DEFAULT_DB_PATH) -> None:
    """Seed all reference data. Safe to re-run (INSERT OR REPLACE)."""
    async with aiosqlite.connect(str(db_path)) as db:

        # Routes
        await db.executemany(
            """INSERT OR REPLACE INTO intent_routing_table
               (id, domain, intent, query_strategy, required_params,
                optional_params, defaults_json, vector_search_filter,
                cache_ttl_seconds)
               VALUES (:id, :domain, :intent, :query_strategy, :required_params,
                       :optional_params, :defaults_json, :vector_search_filter,
                       :cache_ttl_seconds)""",
            ROUTES
        )

        # Entities
        await db.executemany(
            """INSERT OR REPLACE INTO materialized_intelligence_view
               (id, entity_type, entity_id, domain, core_record,
                related_records, recent_events, knowledge_hits,
                last_refreshed, knowledge_refresh_needed)
               VALUES (:id, :entity_type, :entity_id, :domain, :core_record,
                       :related_records, :recent_events, :knowledge_hits,
                       :last_refreshed, :knowledge_refresh_needed)""",
            ENTITIES
        )

        # Knowledge docs — clear and reinsert to keep FTS5 content-sync clean
        await db.execute("DELETE FROM knowledge_base")
        await db.executemany(
            """INSERT INTO knowledge_base
               (id, domain, content, citation, confidence,
                source_tier, last_verified)
               VALUES (:id, :domain, :content, :citation, :confidence,
                       :source_tier, :last_verified)""",
            KNOWLEDGE_DOCS
        )

        # Rebuild FTS index from content table
        await db.execute(
            "INSERT INTO knowledge_fts(knowledge_fts) VALUES('rebuild')"
        )

        await db.commit()

    print(f"Seed complete: {db_path}")
    print(f"  Routes:    {len(ROUTES)}")
    print(f"  Entities:  {len(ENTITIES)}")
    print(f"  Knowledge: {len(KNOWLEDGE_DOCS)}")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DB_PATH
    asyncio.run(seed_database(path))
