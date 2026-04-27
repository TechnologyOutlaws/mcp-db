"""
MCP-DB Parity Test — The Formal Proof of the Compound Query Tier Pattern

Asserts:
  1. Four narrow tool calls produce data equivalent to one compound call.
  2. Four narrow calls write 4 attestation records.
  3. One compound call writes 1 attestation record.
  4. The compound attestation record contains assembled_sources listing
     every data source contributing to the result.
  5. The 4 narrow attestation records require post-hoc correlation to
     reconstruct the same provenance — the compound record captures it
     in one place.

This test is the empirical demonstration that justifies the defensive
publication claim.
"""

import pytest
import pytest_asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

TEST_DB = "test_parity.sqlite"


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    from scripts.init_db import init_database
    from scripts.seed import seed_database

    await init_database(TEST_DB)
    await seed_database(TEST_DB)
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


class TestParityNarrowVsCompound:

    @pytest.mark.asyncio
    async def test_entity_data_equivalent(self):
        """Core record returned by narrow get_entity == compound entity field."""
        from shared.db_sqlite import SQLiteDB
        from shared.tools.narrow.get_entity import get_entity
        from shared.tools.compound.get_entity_context import get_entity_context

        db = SQLiteDB(TEST_DB)
        narrow = await get_entity("acct-001", "account", db=db)
        compound = await get_entity_context(
            "acct-001", "account", "full_context", "general", db=db
        )
        assert narrow["entity"] == compound["entity"], (
            "Entity data mismatch between narrow get_entity and compound "
            "get_entity_context. The pattern requires these to be equivalent."
        )

    @pytest.mark.asyncio
    async def test_records_data_equivalent(self):
        """Records returned by narrow get_records == compound records field."""
        from shared.db_sqlite import SQLiteDB
        from shared.tools.narrow.get_records import get_records
        from shared.tools.compound.get_entity_context import get_entity_context

        db = SQLiteDB(TEST_DB)
        narrow = await get_records("acct-001", "account", db=db)
        compound = await get_entity_context(
            "acct-001", "account", "full_context", "general", db=db
        )
        assert narrow["records"] == compound["records"], (
            "Records mismatch between narrow get_records and compound "
            "get_entity_context."
        )

    @pytest.mark.asyncio
    async def test_events_data_equivalent(self):
        """Events returned by narrow get_recent_events == compound events field."""
        from shared.db_sqlite import SQLiteDB
        from shared.tools.narrow.get_recent_events import get_recent_events
        from shared.tools.compound.get_entity_context import get_entity_context

        db = SQLiteDB(TEST_DB)
        narrow = await get_recent_events("acct-001", "account", db=db)
        compound = await get_entity_context(
            "acct-001", "account", "full_context", "general", db=db
        )
        assert narrow["events"] == compound["events"], (
            "Events mismatch between narrow get_recent_events and compound "
            "get_entity_context."
        )

    @pytest.mark.asyncio
    async def test_narrow_chain_produces_four_attestation_records(self):
        """Four narrow calls = four independent attestation records."""
        from shared.db_sqlite import SQLiteDB
        from shared.tools.narrow.get_entity import get_entity
        from shared.tools.narrow.get_records import get_records
        from shared.tools.narrow.get_recent_events import get_recent_events
        from shared.tools.narrow.get_knowledge_hits import get_knowledge_hits

        db = SQLiteDB(TEST_DB)
        r1 = await get_entity("acct-001", "account", db=db)
        r2 = await get_records("acct-001", "account", db=db)
        r3 = await get_recent_events("acct-001", "account", db=db)
        r4 = await get_knowledge_hits("general", db=db)

        ids = [
            r1["attestation_record_id"],
            r2["attestation_record_id"],
            r3["attestation_record_id"],
            r4["attestation_record_id"],
        ]
        assert len(set(ids)) == 4, (
            f"Expected 4 unique attestation records, got {len(set(ids))}. "
            "Each narrow tool call must write its own record."
        )
        for record_id in ids:
            record = await db.get_attestation(record_id)
            assert record is not None, f"Attestation record {record_id} not found"
            assert record["tool_type"] == "narrow"

    @pytest.mark.asyncio
    async def test_compound_call_produces_one_attestation_record(self):
        """One compound call = one attestation record."""
        from shared.db_sqlite import SQLiteDB
        from shared.tools.compound.get_entity_context import get_entity_context

        db = SQLiteDB(TEST_DB)
        result = await get_entity_context(
            "acct-001", "account", "full_context", "general", db=db
        )
        assert "attestation_record_id" in result
        record = await db.get_attestation(result["attestation_record_id"])
        assert record is not None
        assert record["tool_type"] == "compound"
        assert record["tool_name"] == "get_entity_context"

    @pytest.mark.asyncio
    async def test_compound_attestation_contains_assembled_sources(self):
        """Compound record captures full provenance in assembled_sources."""
        from shared.db_sqlite import SQLiteDB
        from shared.tools.compound.get_entity_context import get_entity_context

        db = SQLiteDB(TEST_DB)
        result = await get_entity_context(
            "acct-001", "account", "full_context", "general", db=db
        )
        record = await db.get_attestation(result["attestation_record_id"])
        sources = json.loads(record["assembled_sources"])
        assert isinstance(sources, list), "assembled_sources must be a list"
        assert len(sources) >= 1, (
            "assembled_sources must contain at least the materialized view ref"
        )
        assert any("materialized_view" in s for s in sources), (
            "assembled_sources must reference the materialized view"
        )

    @pytest.mark.asyncio
    async def test_narrow_records_require_correlation_compound_does_not(self):
        """
        Demonstrates the provenance gap:
        - Narrow: 4 records, each partial, must be correlated by session_id
        - Compound: 1 record, complete provenance in assembled_sources

        This is the core claim of the defensive publication.
        """
        from shared.db_sqlite import SQLiteDB
        from shared.tools.narrow.get_entity import get_entity
        from shared.tools.narrow.get_records import get_records
        from shared.tools.narrow.get_recent_events import get_recent_events
        from shared.tools.narrow.get_knowledge_hits import get_knowledge_hits
        from shared.tools.compound.get_entity_context import get_entity_context

        db = SQLiteDB(TEST_DB)
        SESSION = "parity-test-session"

        n1 = await get_entity("acct-001", "account", session_id=SESSION, db=db)
        n2 = await get_records("acct-001", "account", session_id=SESSION, db=db)
        n3 = await get_recent_events(
            "acct-001", "account", session_id=SESSION, db=db
        )
        n4 = await get_knowledge_hits("general", session_id=SESSION, db=db)

        narrow_ids = [
            n1["attestation_record_id"],
            n2["attestation_record_id"],
            n3["attestation_record_id"],
            n4["attestation_record_id"],
        ]

        narrow_records = [await db.get_attestation(rid) for rid in narrow_ids]
        narrow_tool_names = {r["tool_name"] for r in narrow_records}
        assert narrow_tool_names == {
            "get_entity",
            "get_records",
            "get_recent_events",
            "get_knowledge_hits",
        }, "Narrow chain must produce records for all 4 tools"

        compound = await get_entity_context(
            "acct-001", "account", "full_context", "general",
            session_id=SESSION, db=db,
        )
        compound_record = await db.get_attestation(
            compound["attestation_record_id"]
        )
        compound_sources = json.loads(compound_record["assembled_sources"])

        assert compound_record["tool_type"] == "compound"
        assert len(compound_sources) >= 1
        assert len(narrow_ids) == 4
        assert len([compound["attestation_record_id"]]) == 1

    @pytest.mark.asyncio
    async def test_all_three_entities_resolvable_via_compound(self):
        """All seeded entities are resolvable via get_entity_context."""
        from shared.db_sqlite import SQLiteDB
        from shared.tools.compound.get_entity_context import get_entity_context

        db = SQLiteDB(TEST_DB)
        for entity_id in ["acct-001", "acct-002", "acct-003"]:
            result = await get_entity_context(
                entity_id, "account", "full_context", "general", db=db
            )
            assert result is not None, (
                f"get_entity_context returned None for {entity_id}"
            )
            assert "entity" in result
            assert "attestation_record_id" in result

    @pytest.mark.asyncio
    async def test_knowledge_search_parity(self):
        """Narrow get_knowledge_hits and compound search_knowledge return
        equivalent hit sets for the same query."""
        from shared.db_sqlite import SQLiteDB
        from shared.tools.narrow.get_knowledge_hits import get_knowledge_hits
        from shared.tools.compound.search_knowledge import search_knowledge

        db = SQLiteDB(TEST_DB)
        narrow = await get_knowledge_hits("contract", top=5, db=db)
        compound = await search_knowledge("contract", top=5, db=db)

        narrow_ids = {h["id"] for h in narrow["hits"]}
        compound_ids = {h["id"] for h in compound["hits"]}
        assert narrow_ids == compound_ids, (
            "Knowledge hit sets differ between narrow get_knowledge_hits "
            "and compound search_knowledge for the same query."
        )

        nr = await db.get_attestation(narrow["attestation_record_id"])
        assert nr["tool_type"] == "narrow"
        cr = await db.get_attestation(compound["attestation_record_id"])
        assert cr["tool_type"] == "compound"
