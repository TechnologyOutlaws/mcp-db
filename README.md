# MCP-DB

**Technology Outlaws LLC — Jason Tesso**

| Approach    | Tool calls | Tokens   | Cost @ $3/MTok |
|-------------|------------|----------|----------------|
| Naive chain | 5          | ~210,000 | ~$0.63         |
| MCP-DB      | 1          | ~42,000  | ~$0.13         |
| Savings     | 80%        | 80%      | 80%            |

## The Problem

Agentic loops chain N tool calls. Each call re-sends the full growing
context window. 5 calls on a 40k-token context = 210k input tokens billed.
MCP-DB collapses N to 1 at the protocol layer. The model asks what it
needs to know — the DB layer assembles it.

## How It Works

```
        Agent
          │
          ▼
      intercept()
          │
      ┌───┴───────────────────┐
      │                       │
      ▼                       ▼
 narrow passthrough     CompoundQueryTier
      │                       │
      │                       ▼
      │                       DB
      │                       │
      └───────────┬───────────┘
                  ▼
           AssembledResult
```

The classifier routes each incoming MCP tool call. Narrow tools pass
through unchanged. Compound tools resolve against a pre-materialized
view via the intent router, returning a single attested payload with a
full `assembled_sources` provenance manifest.

## Quick Start

```bash
git clone https://github.com/TechnologyOutlaws/mcp-db.git
cd mcp-db
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/macOS
pip install -r requirements.txt
python scripts/init_db.py
python scripts/seed.py
python server.py
```

Run the test suite:

```bash
python -m pytest tests/ -v
```

Expected: **91 tests, all green.**

## License

MIT — see [LICENSE](./LICENSE).

Architecture covered under pending USPTO patent filed by Technology Outlaws LLC. See NOTICE.md.
