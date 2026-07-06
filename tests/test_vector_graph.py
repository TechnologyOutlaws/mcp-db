"""
MCP-DB Vector-Graph Tests

Covers the net-new vector-graph capability:
  - VectorGraphDB abstract base exposes the 4 required methods
  - SQLite vector_search returns ranked-by-cosine-similarity results
  - SQLite graph_traverse returns the expected BFS path, edge-type filtered
  - SQLite upsert_node + upsert_edge round-trip
  - db_factory routes sqlite (default) and cosmos and both expose the methods
  - The new compound graph tool is registered and dispatchable in the server

Pure-Python SQLite vector approach (no native extension, no azure deps in the
SQLite path) — consistent with the repo ethos: works offline, no credentials.
"""

import pytest
import pytest_asyncio
import inspect
import json
import os
import sys
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

TEST_DB = "test_vector_graph.sqlite"


@pytest_asyncio.fixture(autouse=True)
async def clean_test_db():
    from scripts.init_db import init_database

    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    await init_database(TEST_DB)
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


# ── Abstract base ─────────────────────────────────────────────────────


class TestVectorGraphBase:

    def test_base_declares_four_abstract_methods(self):
        from shared.vector_graph import VectorGraphDB

        for method in (
            "vector_search",
            "graph_traverse",
            "upsert_node",
            "upsert_edge",
        ):
            assert hasattr(VectorGraphDB, method), f"missing {method}"
        abstract = VectorGraphDB.__abstractmethods__
        assert {
            "vector_search",
            "graph_traverse",
            "upsert_node",
            "upsert_edge",
        } <= abstract

    def test_base_cannot_be_instantiated(self):
        from shared.vector_graph import VectorGraphDB

        with pytest.raises(TypeError):
            VectorGraphDB()

    def test_sqlite_is_a_vector_graph_db(self):
        from shared.vector_graph import VectorGraphDB
        from shared.db_sqlite import SQLiteDB

        assert issubclass(SQLiteDB, VectorGraphDB)


# ── SQLite implementation ─────────────────────────────────────────────


class TestSQLiteVectorGraph:

    @pytest.mark.asyncio
    async def test_upsert_node_round_trip(self):
        from shared.db_sqlite import SQLiteDB

        db = SQLiteDB(TEST_DB)
        await db.upsert_node(
            "n-1", "account", {"name": "Alpha"}, [1.0, 0.0, 0.0]
        )
        results = await db.vector_search([1.0, 0.0, 0.0], top_k=1)
        assert len(results) == 1
        assert results[0]["node_id"] == "n-1"
        assert results[0]["node_type"] == "account"
        assert json.loads(results[0]["properties"])["name"] == "Alpha"

    @pytest.mark.asyncio
    async def test_upsert_node_is_idempotent(self):
        from shared.db_sqlite import SQLiteDB

        db = SQLiteDB(TEST_DB)
        await db.upsert_node("n-1", "account", {"v": 1}, [1.0, 0.0])
        await db.upsert_node("n-1", "account", {"v": 2}, [1.0, 0.0])
        results = await db.vector_search([1.0, 0.0], top_k=5)
        assert len(results) == 1
        assert json.loads(results[0]["properties"])["v"] == 2

    @pytest.mark.asyncio
    async def test_vector_search_returns_ranked_results(self):
        from shared.db_sqlite import SQLiteDB

        db = SQLiteDB(TEST_DB)
        await db.upsert_node("close", "account", {}, [1.0, 0.0, 0.0])
        await db.upsert_node("mid", "account", {}, [0.7, 0.7, 0.0])
        await db.upsert_node("far", "account", {}, [0.0, 0.0, 1.0])

        results = await db.vector_search([1.0, 0.0, 0.0], top_k=3)
        ids = [r["node_id"] for r in results]
        assert ids == ["close", "mid", "far"], f"got {ids}"
        # scores monotonically non-increasing
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_vector_search_respects_top_k(self):
        from shared.db_sqlite import SQLiteDB

        db = SQLiteDB(TEST_DB)
        for i in range(5):
            await db.upsert_node(f"n-{i}", "account", {}, [float(i), 1.0])
        results = await db.vector_search([1.0, 1.0], top_k=2)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_vector_search_filters_by_node_type(self):
        from shared.db_sqlite import SQLiteDB

        db = SQLiteDB(TEST_DB)
        await db.upsert_node("a", "account", {}, [1.0, 0.0])
        await db.upsert_node("c", "contract", {}, [1.0, 0.0])
        results = await db.vector_search(
            [1.0, 0.0], top_k=5, filters={"node_type": "contract"}
        )
        assert len(results) == 1
        assert results[0]["node_id"] == "c"

    @pytest.mark.asyncio
    async def test_vector_search_empty_returns_empty(self):
        from shared.db_sqlite import SQLiteDB

        db = SQLiteDB(TEST_DB)
        results = await db.vector_search([1.0, 0.0], top_k=5)
        assert results == []

    @pytest.mark.asyncio
    async def test_upsert_edge_and_graph_traverse_path(self):
        from shared.db_sqlite import SQLiteDB

        db = SQLiteDB(TEST_DB)
        # a -> b -> c chain
        for nid in ("a", "b", "c", "d"):
            await db.upsert_node(nid, "account", {}, [1.0, 0.0])
        await db.upsert_edge("a", "b", "owns", 1.0)
        await db.upsert_edge("b", "c", "owns", 1.0)
        await db.upsert_edge("c", "d", "owns", 1.0)

        # depth 2 from a should reach b and c, not d
        result = await db.graph_traverse("a", depth=2)
        reached = {n["node_id"] for n in result["nodes"]}
        assert "b" in reached
        assert "c" in reached
        assert "d" not in reached
        assert "a" not in reached  # start node excluded from reached set

    @pytest.mark.asyncio
    async def test_graph_traverse_filters_by_edge_type(self):
        from shared.db_sqlite import SQLiteDB

        db = SQLiteDB(TEST_DB)
        for nid in ("a", "b", "c"):
            await db.upsert_node(nid, "account", {}, [1.0, 0.0])
        await db.upsert_edge("a", "b", "owns", 1.0)
        await db.upsert_edge("a", "c", "references", 1.0)

        result = await db.graph_traverse("a", depth=1, edge_types=["owns"])
        reached = {n["node_id"] for n in result["nodes"]}
        assert reached == {"b"}

    @pytest.mark.asyncio
    async def test_graph_traverse_unknown_start_returns_empty(self):
        from shared.db_sqlite import SQLiteDB

        db = SQLiteDB(TEST_DB)
        result = await db.graph_traverse("nope", depth=2)
        assert result["nodes"] == []
        assert result["edges"] == []


# ── db_factory routing ────────────────────────────────────────────────


class TestFactoryRouting:

    def test_factory_default_is_sqlite_with_vector_graph(self, monkeypatch):
        monkeypatch.delenv("DB_VARIANT", raising=False)
        from shared.db_factory import get_db
        from shared.vector_graph import VectorGraphDB

        db = get_db()
        assert isinstance(db, VectorGraphDB)
        for m in ("vector_search", "graph_traverse", "upsert_node", "upsert_edge"):
            assert callable(getattr(db, m))

    def test_factory_cosmos_exposes_vector_graph(self, monkeypatch):
        monkeypatch.setenv("DB_VARIANT", "cosmos")
        monkeypatch.setenv("COSMOS_ENDPOINT", "https://fake.example.com")
        monkeypatch.setenv("COSMOS_DATABASE", "mcp-db")
        with patch("shared.db_cosmos.CosmosClient"), patch(
            "shared.db_cosmos.DefaultAzureCredential"
        ):
            from shared.db_factory import get_db
            from shared.vector_graph import VectorGraphDB

            db = get_db()
            assert isinstance(db, VectorGraphDB)
            for m in (
                "vector_search",
                "graph_traverse",
                "upsert_node",
                "upsert_edge",
            ):
                assert callable(getattr(db, m))


# ── Compound graph tool ───────────────────────────────────────────────


class TestQueryGraphTool:

    @pytest.mark.asyncio
    async def test_query_graph_tool_assembles_and_attests(self):
        from shared.db_sqlite import SQLiteDB
        from shared.tools.compound.query_graph import query_graph

        db = SQLiteDB(TEST_DB)
        await db.upsert_node("seed", "account", {"name": "Seed"}, [1.0, 0.0, 0.0])
        await db.upsert_node("neighbor", "account", {}, [0.9, 0.1, 0.0])
        await db.upsert_edge("seed", "neighbor", "owns", 1.0)

        result = await query_graph(
            query_vector=[1.0, 0.0, 0.0],
            top_k=1,
            depth=1,
            session_id="sess-1",
            db=db,
        )
        assert "vector_hits" in result
        assert "subgraph" in result
        assert "assembled_sources" in result
        assert "attestation_record_id" in result
        # one attestation record written
        record = await db.get_attestation(result["attestation_record_id"])
        assert record is not None
        assert record["tool_type"] == "compound"
        assert record["tool_name"] == "query_graph"

    @pytest.mark.asyncio
    async def test_query_graph_no_seed_hit_returns_empty_subgraph(self):
        from shared.db_sqlite import SQLiteDB
        from shared.tools.compound.query_graph import query_graph

        db = SQLiteDB(TEST_DB)
        result = await query_graph(
            query_vector=[1.0, 0.0],
            top_k=5,
            depth=2,
            session_id="sess-2",
            db=db,
        )
        assert result["vector_hits"] == []
        assert result["subgraph"]["nodes"] == []


# ── Server registration ───────────────────────────────────────────────


class TestServerRegistersQueryGraph:

    @pytest.mark.asyncio
    async def test_list_tools_includes_query_graph(self):
        import server

        tools = await server.list_tools()
        names = {t.name for t in tools}
        assert "query_graph" in names

    @pytest.mark.asyncio
    async def test_query_graph_schema_exposes_intent_and_query_vector(self):
        import server

        tools = await server.list_tools()
        tool = next(t for t in tools if t.name == "query_graph")
        props = tool.inputSchema["properties"]
        # spec contract: seed by text intent, precomputed vector, or seed node —
        # so none is individually required.
        assert "intent" in props
        assert "query_vector" in props
        assert "seed_node_id" in props
        assert tool.inputSchema["required"] == []

    @pytest.mark.asyncio
    async def test_call_tool_routes_query_graph(self):
        import server

        mock_result = {
            "vector_hits": [{"node_id": "seed", "score": 1.0}],
            "subgraph": {"nodes": [], "edges": []},
            "assembled_sources": ["vector::seed"],
            "attestation_record_id": "qg-uuid",
        }
        with patch(
            "shared.tools.compound.query_graph.query_graph",
            new=AsyncMock(return_value=mock_result),
        ):
            result = await server.call_tool(
                "query_graph", {"query_vector": [1.0, 0.0]}
            )
        assert len(result) == 1
        parsed = json.loads(result[0].text)
        assert parsed["vector_hits"][0]["node_id"] == "seed"
