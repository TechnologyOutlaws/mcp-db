# MCP-DB Settled Decisions
_Do not undo these without explicit JT approval and a documented reason._

## SD-01 — SQLite for local dev variant
aiosqlite over sqlite3. Async-first, consistent with MCP async model.
No cloud account required to run tests or demo the pattern.
Do not replace with Postgres, DuckDB, or any other engine for the local variant.

## SD-02 — In-process dict cache for route table
TTL-based in-memory dict in shared/cache.py. No Redis. No external cache.
The reference impl must run with zero external services in SQLite mode.
Do not add Redis as a dependency.

## SD-03 — FTS5 for local knowledge search
SQLite FTS5 virtual table on knowledge_base.
No vector DB, no embedding model, no Pinecone, no Qdrant.
FTS5 is sufficient for the reference impl and keeps the dependency count at zero.

## SD-04 — MIT license
All code MIT. Any new dependency must be MIT, Apache 2.0, or BSD.
AGPLv3 is hard-blocked — it would infect the reference impl.
Check license before adding any pip package.

## SD-05 — Generic domain only
Entity / record / knowledge base. No vertical-specific terminology.
No legal, medical, financial, or proprietary domain language anywhere
in the codebase. The pattern must be domain-neutral.

## SD-06 — No proprietary references
No Marcella. No MCF protocol. No Technology Outlaws internal architecture.
The repo is public-facing and establishes prior art. Keep it clean.

## SD-07 — DefaultAzureCredential only in Cosmos variant
No connection strings. No API keys. No account keys.
KV URI from env var KEY_VAULT_URI. Cosmos endpoint from env var COSMOS_ENDPOINT.
If az login is not run locally, the Cosmos variant will fail — that is expected.
The SQLite variant always works offline.
