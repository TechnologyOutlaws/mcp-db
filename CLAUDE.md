# MCP-DB — Claude Code Standing Instructions

## Project Identity
- Repo: C:\mcp-db (ADO: TechnologyOutlaws/MCP-DB)
- Purpose: Standalone reference implementation of the DB-backed Compound
  Query Tier pattern for MCP servers. Defensive publication project.
  Open-source. No proprietary dependencies.
- Stack: Python 3.11, MCP SDK, SQLite (local), Azure Cosmos DB (cloud variant)
- Owner: Technology Outlaws LLC

## Prime Directive
The answer is the finished product. Not the plan. Not the outline.
Read boil-the-ocean-SKILL.md before every session.

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

6. SECURITY CHECK. Run security-check.md before every commit.
   No secrets in code. No hardcoded endpoints. No API keys.

7. CONTINUATION FILE. Every session ends with a written
   continuation file naming: what shipped, what's next, blockers.

## Architecture — Hard Rules

- SQLite variant: zero Azure dependencies. Runs offline. No imports
  from azure-* packages in shared/db_sqlite.py or tools/.
- Cosmos variant: DefaultAzureCredential ONLY. No connection strings.
  No API keys. KV URI from env var KEY_VAULT_URI.
- Secrets: read from .env locally, Key Vault in deployed variant.
  Never hardcode. Never commit .env.
- No proprietary references: no Marcella, no Technology Outlaws
  internal architecture, no MCF protocol. Generic domain only.
- License: MIT. Verify any new dependency is MIT/Apache/BSD.
  AGPLv3 is blocked.

## Stack Reference

| Component         | SQLite variant      | Cosmos variant              |
|-------------------|---------------------|-----------------------------|
| DB driver         | aiosqlite           | azure-cosmos                |
| Auth              | n/a                 | DefaultAzureCredential      |
| Secret store      | .env file           | Azure Key Vault (your-keyvault) |
| Telemetry         | stdout              | App Insights (your-app-insights)  |
| Route cache       | in-process dict TTL | in-process dict TTL         |

## Environment Variables (.env — never committed)

COSMOS_ENDPOINT=https://your-cosmos-account.documents.azure.com:443/
COSMOS_DATABASE=mcp-db
KEY_VAULT_URI=https://your-keyvault.vault.azure.net/
AZURE_SUBSCRIPTION_ID=your-subscription-id

## Cosmos Containers (cloud variant)

| Container                      | Partition Key |
|-------------------------------|---------------|
| materialized_intelligence_view | /tenant_id    |
| intent_routing_table           | /domain       |
| compound_attestation_log       | /tenant_id    |

## Settled Decisions — Do Not Re-Litigate

See .claude/references/settled-decisions.md for full registry.

Fast reference:
- SQLite for local dev — no cloud variant required to run tests
- aiosqlite over sqlite3 — async-first, consistent with MCP async model
- In-process dict cache for route table — no Redis dependency
- FTS5 for local knowledge search — no vector DB required for reference impl
- MIT license — enables defensive publication and open-source distribution
- Generic domain (entity/record/knowledge) — no vertical specificity

## Build Sequence (remaining sessions)

- Prompt C: SQLite schema (init_db.py) + seed data (seed.py)
- Prompt D: shared/db_sqlite.py + shared/db_cosmos.py (both variants)
- Prompt E: shared/intent_router.py + shared/cache.py + shared/attestation.py
- Prompt F: Narrow tools — get_entity, get_records, get_recent_events, get_knowledge_hits
- Prompt G: Compound tools — get_entity_context, search_knowledge + server.py
- Prompt H: Tests — test_intent_router, test_compound_tools, test_attestation, test_narrow_parity
- Prompt I: PRIOR_ART.md + README final polish + .env.example

## Read Before Building
- .claude/skills/boil-the-ocean-SKILL.md — execution standard
- .claude/references/settled-decisions.md — do not undo these
- .claude/references/security-check.md — run before every commit
