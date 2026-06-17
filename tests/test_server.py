"""
MCP-DB Server Tests
Verifies tool registration and call_tool routing.
Uses mocked tool functions — no live DB calls.
"""

import pytest
import json
import os
import sys
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestServerToolRegistration:

    @pytest.mark.asyncio
    async def test_list_tools_returns_seven(self):
        import server

        tools = await server.list_tools()
        assert len(tools) == 7

    @pytest.mark.asyncio
    async def test_all_tool_names_registered(self):
        import server

        tools = await server.list_tools()
        names = {t.name for t in tools}
        expected = {
            "get_entity_context",
            "search_knowledge",
            "get_entity",
            "get_records",
            "get_recent_events",
            "get_knowledge_hits",
            "query_graph",
        }
        assert names == expected

    @pytest.mark.asyncio
    async def test_compound_tools_have_descriptions(self):
        import server

        tools = await server.list_tools()
        compound = {
            t.name: t
            for t in tools
            if t.name in ("get_entity_context", "search_knowledge")
        }
        for name, tool in compound.items():
            assert tool.description, f"{name} must have a description"
            assert len(tool.description) > 20, (
                f"{name} description too short to be useful"
            )

    @pytest.mark.asyncio
    async def test_get_entity_context_schema_has_required_entity_id(self):
        import server

        tools = await server.list_tools()
        tool = next(t for t in tools if t.name == "get_entity_context")
        assert "entity_id" in tool.inputSchema["properties"]
        assert "entity_id" in tool.inputSchema["required"]

    @pytest.mark.asyncio
    async def test_search_knowledge_schema_has_required_query(self):
        import server

        tools = await server.list_tools()
        tool = next(t for t in tools if t.name == "search_knowledge")
        assert "query" in tool.inputSchema["properties"]
        assert "query" in tool.inputSchema["required"]

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error_text(self):
        import server

        result = await server.call_tool("nonexistent_tool", {})
        assert len(result) == 1
        assert "Unknown tool" in result[0].text


class TestServerCallToolRouting:

    @pytest.mark.asyncio
    async def test_routes_get_entity_context(self):
        import server

        mock_result = {
            "entity": {"name": "Alpha"},
            "records": [],
            "events": [],
            "knowledge_hits": [],
            "assembled_sources": ["materialized_view::test"],
            "attestation_record_id": "test-uuid",
        }
        with patch(
            "shared.tools.compound.get_entity_context.get_entity_context",
            new=AsyncMock(return_value=mock_result),
        ):
            result = await server.call_tool(
                "get_entity_context", {"entity_id": "acct-001"}
            )
        assert len(result) == 1
        parsed = json.loads(result[0].text)
        assert parsed["entity"]["name"] == "Alpha"

    @pytest.mark.asyncio
    async def test_routes_search_knowledge(self):
        import server

        mock_result = {
            "hits": [{"id": "kb-001", "citation": "Test \u00a7 1"}],
            "assembled_sources": ["fts::kb-001"],
            "attestation_record_id": "test-uuid-2",
        }
        with patch(
            "shared.tools.compound.search_knowledge.search_knowledge",
            new=AsyncMock(return_value=mock_result),
        ):
            result = await server.call_tool(
                "search_knowledge", {"query": "contract"}
            )
        assert len(result) == 1
        parsed = json.loads(result[0].text)
        assert len(parsed["hits"]) == 1

    @pytest.mark.asyncio
    async def test_routes_get_entity(self):
        import server

        mock_result = {
            "entity": {"name": "Alpha"},
            "attestation_record_id": "narrow-uuid",
        }
        with patch(
            "shared.tools.narrow.get_entity.get_entity",
            new=AsyncMock(return_value=mock_result),
        ):
            result = await server.call_tool(
                "get_entity", {"entity_id": "acct-001"}
            )
        assert len(result) == 1
        parsed = json.loads(result[0].text)
        assert parsed["entity"]["name"] == "Alpha"

    @pytest.mark.asyncio
    async def test_get_entity_context_null_result_returns_null_string(self):
        """Verify server handles None return from tool gracefully."""
        import server

        with patch(
            "shared.tools.compound.get_entity_context.get_entity_context",
            new=AsyncMock(return_value=None),
        ):
            result = await server.call_tool(
                "get_entity_context", {"entity_id": "missing"}
            )
        assert result[0].text == "null"
