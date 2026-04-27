"""
MCP-DB — MCP Server
Registers all 6 tools: 4 narrow + 2 compound.
Runs via stdio transport (standard MCP pattern).
DB variant controlled by DB_VARIANT env var (default: sqlite).

Usage:
  python server.py                    # SQLite variant
  DB_VARIANT=cosmos python server.py  # Cosmos variant (requires az login)
"""

import asyncio
import json

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

from shared.db_factory import get_db

_db = get_db()

app = Server("mcp-db")


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name == "get_entity_context":
        from shared.tools.compound.get_entity_context import get_entity_context

        result = await get_entity_context(
            entity_id=arguments["entity_id"],
            entity_type=arguments.get("entity_type", "account"),
            intent=arguments.get("intent", "full_context"),
            domain=arguments.get("domain", "general"),
            include_knowledge=arguments.get("include_knowledge", True),
            knowledge_limit=arguments.get("knowledge_limit", 5),
            include_events=arguments.get("include_events", True),
            session_id=arguments.get("session_id", "anonymous"),
            db=_db,
        )
        return [
            types.TextContent(
                type="text",
                text=json.dumps(result, indent=2) if result else "null",
            )
        ]

    elif name == "search_knowledge":
        from shared.tools.compound.search_knowledge import search_knowledge

        result = await search_knowledge(
            query=arguments["query"],
            top=arguments.get("top", 5),
            tier_min=arguments.get("tier_min", 1),
            domain=arguments.get("domain", "general"),
            session_id=arguments.get("session_id", "anonymous"),
            db=_db,
        )
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_entity":
        from shared.tools.narrow.get_entity import get_entity

        result = await get_entity(
            entity_id=arguments["entity_id"],
            entity_type=arguments.get("entity_type", "account"),
            session_id=arguments.get("session_id", "anonymous"),
            db=_db,
        )
        return [
            types.TextContent(
                type="text",
                text=json.dumps(result, indent=2) if result else "null",
            )
        ]

    elif name == "get_records":
        from shared.tools.narrow.get_records import get_records

        result = await get_records(
            entity_id=arguments["entity_id"],
            entity_type=arguments.get("entity_type", "account"),
            session_id=arguments.get("session_id", "anonymous"),
            db=_db,
        )
        return [
            types.TextContent(
                type="text",
                text=json.dumps(result, indent=2) if result else "null",
            )
        ]

    elif name == "get_recent_events":
        from shared.tools.narrow.get_recent_events import get_recent_events

        result = await get_recent_events(
            entity_id=arguments["entity_id"],
            entity_type=arguments.get("entity_type", "account"),
            limit=arguments.get("limit", 10),
            session_id=arguments.get("session_id", "anonymous"),
            db=_db,
        )
        return [
            types.TextContent(
                type="text",
                text=json.dumps(result, indent=2) if result else "null",
            )
        ]

    elif name == "get_knowledge_hits":
        from shared.tools.narrow.get_knowledge_hits import get_knowledge_hits

        result = await get_knowledge_hits(
            query=arguments["query"],
            top=arguments.get("top", 5),
            tier_min=arguments.get("tier_min", 1),
            domain=arguments.get("domain", "general"),
            session_id=arguments.get("session_id", "anonymous"),
            db=_db,
        )
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

    else:
        return [types.TextContent(type="text", text=f"Unknown tool: {name}")]


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="get_entity_context",
            description=(
                "Returns assembled entity context in one call. "
                "Use instead of chaining get_entity + get_records + "
                "get_recent_events + get_knowledge_hits. "
                "Produces one attestation record covering all assembled sources."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_id": {
                        "type": "string",
                        "description": "Entity identifier",
                    },
                    "entity_type": {"type": "string", "default": "account"},
                    "intent": {
                        "type": "string",
                        "default": "full_context",
                        "enum": ["full_context", "summary", "audit_context"],
                    },
                    "domain": {"type": "string", "default": "general"},
                    "include_knowledge": {"type": "boolean", "default": True},
                    "knowledge_limit": {"type": "integer", "default": 5},
                    "include_events": {"type": "boolean", "default": True},
                    "session_id": {"type": "string", "default": "anonymous"},
                },
                "required": ["entity_id"],
            },
        ),
        types.Tool(
            name="search_knowledge",
            description=(
                "Attested knowledge base search. No entity context required. "
                "Use for free-text queries against the knowledge base. "
                "Produces one attestation record per call."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query",
                    },
                    "top": {"type": "integer", "default": 5},
                    "tier_min": {"type": "integer", "default": 1},
                    "domain": {"type": "string", "default": "general"},
                    "session_id": {"type": "string", "default": "anonymous"},
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="get_entity",
            description=(
                "Returns core record for a single entity. "
                "Narrow tool — use get_entity_context for assembled context."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string"},
                    "entity_type": {"type": "string", "default": "account"},
                    "session_id": {"type": "string", "default": "anonymous"},
                },
                "required": ["entity_id"],
            },
        ),
        types.Tool(
            name="get_records",
            description="Returns related records list for a single entity.",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string"},
                    "entity_type": {"type": "string", "default": "account"},
                    "session_id": {"type": "string", "default": "anonymous"},
                },
                "required": ["entity_id"],
            },
        ),
        types.Tool(
            name="get_recent_events",
            description="Returns recent events for a single entity.",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string"},
                    "entity_type": {"type": "string", "default": "account"},
                    "limit": {"type": "integer", "default": 10},
                    "session_id": {"type": "string", "default": "anonymous"},
                },
                "required": ["entity_id"],
            },
        ),
        types.Tool(
            name="get_knowledge_hits",
            description="FTS knowledge base search. Narrow tool.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "top": {"type": "integer", "default": 5},
                    "tier_min": {"type": "integer", "default": 1},
                    "domain": {"type": "string", "default": "general"},
                    "session_id": {"type": "string", "default": "anonymous"},
                },
                "required": ["query"],
            },
        ),
    ]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream, write_stream, app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
