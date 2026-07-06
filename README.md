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

Expected: **126 tests, all green.**

## Integration Path 3 — Graph / Vector

`mcp-db` serves the same backend three ways. Narrow tools do point reads;
compound tools return pre-assembled context in one call; and the graph/vector
path traverses typed relationships combined with semantic similarity.

The `query_graph` tool seeds by semantic similarity to a text `intent` (or an
explicit `seed_node_id`, or a precomputed `query_vector`), then traverses the
typed-edge neighbourhood and returns a connected subgraph — with one attestation
record enumerating every node touched.

```python
from shared.tools.compound.query_graph import query_graph

result = await query_graph(intent="acme's open invoices", depth=2)
# -> { nodes, edges, paths, vector_hits, assembled_sources, attestation_record_id }
```

Domain-neutral model: node types `entity | record | event | knowledge_chunk`;
edge types `relates_to | references | derived_from | cites | belongs_to`. The
graph is populated from the same data the point-read tools already return.

Embeddings are pluggable via `EMBED_PROVIDER` (`shared/embeddings.py`): the
default `hash` provider is dependency-free and offline (the CI default), with
`openai` and `local` (sentence-transformers) available as lazy, optional
providers. `EMBED_DIM` keeps the query dimension aligned with the stored vectors.
Vector similarity uses pure-Python cosine — no native extension, no cloud
dependency, consistent with this repo's offline-first design.

**Upgrade path:** `mcp-db` is the open, portable substrate. The same backend
abstraction and tool surface can be wrapped by a compliance-hardening layer with
attestation sealing for regulated workloads — the tool contract is preserved
across the open and hardened variants.

## License

MIT — see [LICENSE](./LICENSE).

Architecture covered under pending USPTO patent filed by Technology Outlaws LLC. See NOTICE.md.
