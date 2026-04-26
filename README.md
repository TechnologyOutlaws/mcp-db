# MCP-DB: DB-Backed Compound Query Tier for MCP Servers

A reference implementation of the **Compound Query Tier** pattern for
Model Context Protocol (MCP) servers. Collapses multi-step AI agent tool
call chains into a single attested call backed by a materialized
intelligence view.

## The Problem

Standard MCP servers expose narrow, single-purpose tools. An agent
assembling context makes N sequential calls:

```
→ get_entity(id)          # round trip 1
→ get_records(id)         # round trip 2
→ search_knowledge(query) # round trip 3
→ get_recent_events(id)   # round trip 4
```

N round trips. N context window blocks. N attestation records to
correlate post-hoc. The agent orchestrates the join.

## The Solution

One call. The server resolves the join against a pre-materialized view.

```
→ get_entity_context(entity_id, intent="full_context")
```

One attestation record. Full provenance over the assembled result.

## Architecture

```
AI Agent
   │  single MCP tool call
   ▼
MCP Server + Compound Query Tier
   ├── Tool Type Classifier (narrow vs compound)
   ├── Intent Router
   │     ├── Route cache (in-process, TTL 300s)
   │     ├── Materialized view lookup (O(1) point-read)
   │     └── Optional FTS/vector augmentation
   └── Attestation Record Write (1 record per compound call)
```

## Quickstart (SQLite — no cloud required)

```bash
git clone https://dev.azure.com/jb0551/TechnologyOutlaws/_git/MCP-DB
cd mcp-db
python -m venv .venv && .venv\Scripts\activate    # Windows
pip install -r requirements.txt
python scripts/init_db.py
python scripts/seed.py
python server.py
```

## Quickstart (Cosmos DB variant)

```bash
cp .env.example .env   # fill in your Azure values
az login
python scripts/init_cosmos.py
python scripts/seed_cosmos.py
python server.py --variant cosmos
```

## Variants

| Variant | DB backend | Auth | Cloud required |
|---------|-----------|------|---------------|
| SQLite  | aiosqlite  | none | No            |
| Cosmos  | azure-cosmos | DefaultAzureCredential | Yes |

## Prior Art

See `PRIOR_ART.md` — defensive publication establishing this pattern
in the prior art record as of April 26, 2026.

## License

MIT
