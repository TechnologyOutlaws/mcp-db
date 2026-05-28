# MCP-DB — Claude Code Standing Instructions

**Owner:** Technology Outlaws LLC
**Author:** Jason Tesso <jt@technologyoutlaws.com>
**Repo:** MCP-DB

## Project Identity
- Repo: C:\mcp-db (ADO: TechnologyOutlaws/MCP-DB)
- Purpose: Standalone reference implementation of the DB-backed Compound
  Query Tier pattern for MCP servers. Defensive publication project.
  Open-source. No proprietary dependencies.
- Stack: Python 3.11, MCP SDK, SQLite (local), Azure Cosmos DB (cloud variant)
- Owner: Technology Outlaws LLC

## Prime Directive
The answer is the finished product. Not the plan. Not the outline.

## Execution Rules (Non-Negotiable)

1. PLAN FIRST. Before writing any code, state the plan:
   steps, sequence, done conditions. Only then execute.

2. ONE TASK PER SESSION. This repo has two variants (SQLite and Cosmos).
   Each module, each tool, each test file = one CC session.
   Never build multiple modules in one prompt.

3. RE-PLAN TRIGGER. If the same error occurs twice: STOP.
   Do not attempt a third pass. Re-plan with a different approach.

4. TDD FIRST. Write the test. Confirm it fails (red).
   Then write the implementation. Confirm it passes (green).
   Never write implementation before tests exist.

5. VERIFY BEFORE DONE. Every session ends with a verifiable
   done checklist. "It should work" is not done.
   Run pytest. Confirm green. Then call it done.

6. SECURITY CHECK. No secrets in code. No hardcoded endpoints.
   No API keys. Run a secrets scan before every commit.

7. CONTINUATION FILE. Every session ends with a written
   continuation file naming: what shipped, what's next, blockers.

## Architecture — Hard Rules

- SQLite variant: zero Azure dependencies. Runs offline. No imports
  from azure-* packages in shared/db_sqlite.py or tools/.
- Cosmos variant: DefaultAzureCredential ONLY. No connection strings.
  No API keys. KV URI from env var KEY_VAULT_URI.
- Secrets: read from .env locally, Key Vault in deployed variant.
  Never hardcode. Never commit .env.
- License: MIT. Verify any new dependency is MIT/Apache/BSD.
  AGPLv3 is blocked.

## Stack Reference

| Component         | SQLite variant      | Cosmos variant              |
|-------------------|---------------------|-----------------------------|
| DB driver         | aiosqlite           | azure-cosmos                |
| Auth              | n/a                 | DefaultAzureCredential      |
| Secret store      | .env file           | Azure Key Vault             |
| Telemetry         | stdout              | App Insights                |
| Route cache       | in-process dict TTL | in-process dict TTL         |

## Environment Variables

See `.env.example` for the variables required by the Cosmos variant.
`.env` is gitignored and must never be committed.

## Cosmos Containers (cloud variant)

| Container                      | Partition Key |
|-------------------------------|---------------|
| materialized_intelligence_view | /tenant_id    |
| intent_routing_table           | /domain       |
| compound_attestation_log       | /tenant_id    |

## Settled Decisions — Do Not Re-Litigate

- SQLite for local dev — no cloud variant required to run tests
- aiosqlite over sqlite3 — async-first, consistent with MCP async model
- In-process dict cache for route table — no Redis dependency
- FTS5 for local knowledge search — no vector DB required for reference impl
- MIT license — enables defensive publication and open-source distribution
- Generic domain (entity/record/knowledge) — no vertical specificity
