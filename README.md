# MCP-DB: DB-Backed Compound Query Tier for MCP Servers

A reference implementation of the **Compound Query Tier** pattern —
a DB-backed middleware layer inside an MCP server that collapses
multi-step AI agent tool call chains into a single attested call.

**Prior art established:** See [PRIOR_ART.md](./PRIOR_ART.md) —
defensive publication dated 2026-04-26.

---

## The Problem

Standard MCP servers expose narrow, single-purpose tools. An agent
assembling context makes N sequential calls:

```
→ get_entity(id)           # call 1 — 1 attestation record
→ get_records(id)          # call 2 — 1 attestation record
→ get_recent_events(id)    # call 3 — 1 attestation record
→ get_knowledge_hits(q)    # call 4 — 1 attestation record
```

**4 round trips. 4 context window blocks. 4 attestation records
requiring post-hoc correlation.** The agent orchestrates the join.

---

## The Solution

One call. The server resolves the join against a pre-materialized view.

```
→ get_entity_context(entity_id, intent="full_context")
```

**1 round trip. 1 context window block. 1 attestation record with
full provenance over the assembled result.**

---

## Architecture

```
AI Agent
   │  single MCP tool call
   ▼
MCP Server + Compound Query Tier
   ├── Tool Type Classifier
   │     narrow  → direct execution (unchanged)
   │     compound → Intent Router
   ├── Intent Router
   │     ├── Route cache (in-process TTLCache, 300s default)
   │     ├── Materialized view lookup (O(1) point-read)
   │     └── Optional FTS knowledge augmentation
   └── Attestation Record Write
         tool_type: "compound"
         assembled_sources: [every source contributing to result]
         result_hash: SHA-256 of assembled payload
```

---

## Parity Proof

| Metric | Narrow chain (4 calls) | Compound call (1 call) |
|--------|----------------------|----------------------|
| MCP tool calls | 4 | 1 |
| Attestation records written | 4 | 1 |
| Provenance per record | Partial | Complete (assembled_sources) |
| Data result | Equivalent | Equivalent |

Verified by `tests/test_parity.py` — 9 formal assertions including
`test_narrow_records_require_correlation_compound_does_not`.

---

## Quickstart — SQLite (no cloud required)

```bash
git clone https://dev.azure.com/jb0551/TechnologyOutlaws/_git/MCP-DB
cd mcp-db
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/Mac
pip install -r requirements.txt
python scripts/init_db.py
python scripts/seed.py
python server.py
```

Expected seed output:
```
Seed complete: mcp_db.sqlite
  Routes:    4
  Entities:  3
  Knowledge: 10
```

Expected server startup: MCP server running on stdio, ready for agent connection.

### Verify with pytest

```bash
python -m pytest tests/ -v
```

Expected: **91 tests, all green.**

---

## Quickstart — Cosmos DB variant

```bash
cp .env.example .env   # fill in your Azure values
az login
python server.py       # DB_VARIANT defaults to sqlite
DB_VARIANT=cosmos python server.py
```

Requires: `az login` with access to your Cosmos DB account.
DefaultAzureCredential only — no connection strings.

---

## Project Structure

```
mcp-db/
├── server.py                          # MCP server — 6 tools registered
├── PRIOR_ART.md                       # Defensive publication (2026-04-26)
├── shared/
│   ├── cache.py                       # In-process TTL cache (no Redis)
│   ├── intent_router.py               # Compound Query Tier core
│   ├── attestation.py                 # SHA-256 attestation record writer
│   ├── db_sqlite.py                   # SQLite backend (offline, zero deps)
│   ├── db_cosmos.py                   # Cosmos backend (DefaultAzureCredential)
│   ├── db_factory.py                  # DB_VARIANT router
│   └── tools/
│       ├── compound/
│       │   ├── get_entity_context.py  # Primary compound tool
│       │   └── search_knowledge.py    # Attested knowledge search
│       └── narrow/
│           ├── get_entity.py
│           ├── get_records.py
│           ├── get_recent_events.py
│           └── get_knowledge_hits.py
├── scripts/
│   ├── init_db.py                     # Schema creation (idempotent)
│   └── seed.py                        # Seed routes, entities, knowledge
└── tests/
    ├── test_schema.py                 # 12 tests
    ├── test_db.py                     # 14 tests
    ├── test_intent_router.py          # 17 tests
    ├── test_narrow_tools.py           # 17 tests
    ├── test_compound_tools.py         # 12 tests
    ├── test_parity.py                 # 9 tests — formal parity proof
    └── test_server.py                 # 10 tests
```

---

## Adapting to Your Stack

### 1. Replace the DB backend

Implement the same 7-method interface as `shared/db_sqlite.py`:
- `get_materialized_view(entity_id, entity_type)`
- `get_route(domain, intent)`
- `search_knowledge(query, top, tier_min)`
- `write_attestation(record)`
- `get_attestation(record_id)`
- `upsert_materialized_view(doc)`
- `get_stale_views()`

Point `shared/db_factory.py` to your implementation via `DB_VARIANT`.

### 2. Replace FTS with vector search

In `shared/db_sqlite.py`, replace the `search_knowledge` FTS5 query
with calls to your vector index (Pinecone, Qdrant, Azure AI Search).
The interface contract — returns `list[dict]` with `id`, `content`,
`citation`, `confidence`, `source_tier` — stays the same.

### 3. Wire the write-side refresh

The `shared/intent_router.py` `_is_stale()` method flags stale views.
In production, wire the refresh to your event system:
- Change feed (Cosmos) → call `db.upsert_materialized_view()`
- Message queue → same
- Timer → query `db.get_stale_views()`, refresh each

### 4. Register your own intents

Add rows to `intent_routing_table`. No code changes required.
Each row maps `(domain, intent)` → query strategy + defaults.

### 5. Add your domain's compound tools

Copy `shared/tools/compound/get_entity_context.py`.
Change `tool_name`, adjust `intent` values, wire to your router.
Register in `server.py`.

---

## The Attestation Record

Every tool call — narrow or compound — writes one attestation record:

```json
{
  "id": "uuid",
  "session_id": "...",
  "tool_name": "get_entity_context",
  "tool_type": "compound",
  "intent": "full_context",
  "domain": "general",
  "entity_id": "acct-001",
  "assembled_sources": [
    "materialized_view::account:acct-001",
    "fts::kb-002",
    "fts::kb-006"
  ],
  "result_hash": "sha256...",
  "timestamp": "2026-04-26T...",
  "latency_ms": 12
}
```

`assembled_sources` is the provenance manifest. For compound calls,
one record captures what 4 narrow records would require correlation to reconstruct.

---

## Prior Art

See [PRIOR_ART.md](./PRIOR_ART.md) — defensive publication establishing
this pattern in the prior art record as of **2026-04-26**.

The five novel combinations covered:
1. Compound Query Tier inside MCP server middleware
2. Intent-to-query-strategy routing table for MCP
3. Materialized view with write-side triggers consumed by MCP tools
4. Single compound attestation record with assembled_sources manifest
5. Staleness-triggered fallback to narrow tool chain

---

## License

MIT — see [LICENSE](./LICENSE)
