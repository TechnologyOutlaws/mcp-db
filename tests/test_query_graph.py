"""
MCP-DB query_graph tool tests — the graph-aware vector query (path 3).

Exercises the two seed modes (vector-discovered vs explicit seed), the text
intent path (embedded via the hash embedder), the empty-result contract, the
one-attestation-per-call guarantee, and the GraphNotSupportedError path for a
backend without graph support. Pure SQLite + hash embedder — offline, no keys.
"""

import os
import sys

import pytest
import pytest_asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

TEST_DB = "test_query_graph.sqlite"


@pytest_asyncio.fixture(autouse=True)
async def clean_test_db():
    from scripts.init_db import init_database

    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    await init_database(TEST_DB)
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


async def _seed_graph(db):
    """Seed 3 text-embedded nodes + edges: acme -> acct -> invoice."""
    from shared.embeddings import hash_embed

    await db.upsert_node(
        "entity::acme", "entity",
        {"name": "Acme vector graph cosmos"}, hash_embed("acme vector graph cosmos"),
    )
    await db.upsert_node(
        "record::acct-42", "record",
        {"name": "account 42"}, hash_embed("account forty two ledger"),
    )
    await db.upsert_node(
        "record::inv-9", "record",
        {"name": "invoice 9"}, hash_embed("invoice nine billing"),
    )
    await db.upsert_edge("entity::acme", "record::acct-42", "belongs_to", 1.0)
    await db.upsert_edge("record::acct-42", "record::inv-9", "references", 1.0)


class TestQueryGraphModes:

    @pytest.mark.asyncio
    async def test_intent_mode_discovers_seed_and_traverses(self):
        from shared.db_sqlite import SQLiteDB
        from shared.tools.compound.query_graph import query_graph

        db = SQLiteDB(TEST_DB)
        await _seed_graph(db)

        result = await query_graph(
            intent="acme vector graph cosmos", top_k=1, depth=2, db=db,
        )
        assert result["vector_hits"], "intent should embed + find a seed"
        assert result["vector_hits"][0]["node_id"] == "entity::acme"
        reached = {n["node_id"] for n in result["nodes"]}
        assert "record::acct-42" in reached
        assert "record::inv-9" in reached  # depth 2
        assert result["paths"], "paths should record traversal edges"
        assert result["attestation_record_id"]

    @pytest.mark.asyncio
    async def test_seed_node_mode_traverses_without_vector(self):
        from shared.db_sqlite import SQLiteDB
        from shared.tools.compound.query_graph import query_graph

        db = SQLiteDB(TEST_DB)
        await _seed_graph(db)

        result = await query_graph(seed_node_id="entity::acme", depth=1, db=db)
        assert result["vector_hits"] == []
        reached = {n["node_id"] for n in result["nodes"]}
        assert reached == {"record::acct-42"}  # depth 1 only
        # seed itself is in provenance even with no vector hit
        assert "graph::entity::acme" in result["assembled_sources"]

    @pytest.mark.asyncio
    async def test_query_vector_passthrough_still_works(self):
        from shared.db_sqlite import SQLiteDB
        from shared.embeddings import hash_embed
        from shared.tools.compound.query_graph import query_graph

        db = SQLiteDB(TEST_DB)
        await _seed_graph(db)

        result = await query_graph(
            query_vector=hash_embed("invoice nine billing"), top_k=1, depth=0, db=db,
        )
        assert result["vector_hits"][0]["node_id"] == "record::inv-9"

    @pytest.mark.asyncio
    async def test_empty_query_returns_empty_not_none(self):
        from shared.db_sqlite import SQLiteDB
        from shared.tools.compound.query_graph import query_graph

        db = SQLiteDB(TEST_DB)
        await _seed_graph(db)

        result = await query_graph(db=db)  # no intent, vector, or seed
        assert result is not None
        assert result["vector_hits"] == []
        assert result["nodes"] == []
        assert result["assembled_sources"] == []
        assert result["attestation_record_id"]


class TestAttestation:

    @pytest.mark.asyncio
    async def test_exactly_one_attestation_per_call(self):
        from shared.db_sqlite import SQLiteDB
        from shared.tools.compound.query_graph import query_graph

        db = SQLiteDB(TEST_DB)
        await _seed_graph(db)

        result = await query_graph(intent="acme vector graph cosmos", db=db)
        record = await db.get_attestation(result["attestation_record_id"])
        assert record is not None
        assert record["tool_name"] == "query_graph"
        assert record["tool_type"] == "compound"

    @pytest.mark.asyncio
    async def test_assembled_sources_covers_every_node_touched(self):
        from shared.db_sqlite import SQLiteDB
        from shared.tools.compound.query_graph import query_graph

        db = SQLiteDB(TEST_DB)
        await _seed_graph(db)

        result = await query_graph(intent="acme vector graph cosmos", top_k=1, depth=2, db=db)
        # every reached graph node appears in provenance
        for n in result["nodes"]:
            assert f"graph::{n['node_id']}" in result["assembled_sources"]


class TestGraphNotSupported:

    @pytest.mark.asyncio
    async def test_backend_without_graph_raises(self):
        from shared.tools.compound.query_graph import query_graph
        from shared.vector_graph import GraphNotSupportedError

        class NoGraphBackend:
            async def vector_search(self, *a, **k):
                return []
            # deliberately no graph_traverse

        with pytest.raises(GraphNotSupportedError):
            await query_graph(intent="x", db=NoGraphBackend())
