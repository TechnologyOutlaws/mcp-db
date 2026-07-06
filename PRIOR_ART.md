# Defensive Publication: DB-Backed Compound Query Tier for Model Context Protocol Servers

**Publication Date:** 2026-04-26
**Field:** Artificial Intelligence Infrastructure / Agent Tool Invocation Protocols
**Keywords:** MCP, Model Context Protocol, AI agents, tool invocation, compound query,
materialized view, intent routing, chain-of-custody, single-call context assembly
**Reference Implementation:** https://dev.azure.com/jb0551/TechnologyOutlaws/_git/MCP-DB

---

## I. TECHNICAL FIELD

This disclosure describes a method and system for reducing multi-step AI agent tool
invocations to a single attested call by embedding a database-backed compound query
tier inside a Model Context Protocol (MCP) server. The method is applicable to any
AI agent runtime that communicates with external tools and data sources via MCP.

---

## II. BACKGROUND

### The MCP Multi-Call Problem

The Model Context Protocol (MCP) is an open protocol for connecting AI language model
agents to external tools, APIs, and data sources. In its standard form, an MCP server
exposes a set of narrow, single-purpose tools. An agent assembles context by calling
these tools sequentially, each call returning a partial result that the agent must
combine with prior results to form a complete picture.

For example, an agent assembling context about a client record might call:

```
→ tool_call: get_client(client_id)
→ tool_call: get_records(client_id)
→ tool_call: search_knowledge_base(domain, query)
→ tool_call: get_recent_events(record_id)
→ tool_call: get_related_documents(record_id)
```

This produces five sequential round trips. Each round trip carries:

- **Latency cost:** each tool call is a network round trip plus server execution
- **Context cost:** each tool-use / tool-result block consumes agent context window
- **Orchestration cost:** the agent must hold intermediate state between calls
- **Error surface:** each call can fail independently; partial results require recovery logic
- **Audit cost:** if each call is independently attested, N calls produce N audit records
  that must be correlated after the fact to reconstruct the agent's reasoning chain

As agent workflows grow more complex — spanning multiple data sources, knowledge
bases, and external APIs — the N-call problem compounds. An agent that makes 20 tool
calls to assemble a complete operational picture is slower, more expensive in tokens,
and more prone to mid-chain failure than one that makes a single well-formed call.

### Prior Art in Adjacent Fields

Database materialized views collapse N-query data assembly into a pre-joined read.
Operating system kernel designs (notably the Windows NT Object Manager and PowerShell's
type system extension to the OS) embed structured data access at the system layer so
applications receive assembled objects rather than raw subsystem calls. The insight
that the OS kernel itself can be queryable — rather than acting merely as a dispatcher
to queryable subsystems — reduces application-layer orchestration to zero.

No prior art applies this principle to the MCP server layer. Existing MCP server
implementations expose narrow tools and leave context assembly to the calling agent.

---

## III. SUMMARY OF THE DISCLOSURE

This disclosure describes a **Compound Query Tier** that can be embedded inside any
MCP server to collapse multi-step agent tool invocations into a single call. The
tier consists of:

1. **A materialized intelligence view** — a continuously-refreshed database document
   that pre-joins data from multiple sources relevant to a given entity or domain.

2. **A persistent intent routing table** — a configuration store mapping agent-declared
   intent strings to query strategies, allowing the MCP server to resolve what the
   agent needs without the agent directing the join sequence.

3. **An in-process Intent Router** — middleware inside the MCP server that intercepts
   compound tool calls, resolves the route, executes the materialized view lookup,
   optionally augments with a vector search slice, assembles the result, and returns
   it to the agent in a single response.

4. **Write-side refresh triggers** — event-driven mechanisms that keep the materialized
   view continuously fresh without requiring query-time computation.

5. **A compound attestation record** — a single audit record sealed at the time of the
   compound call that captures full provenance over the assembled result, including
   every source document contributing to the assembly.

The result: an agent makes one call, receives assembled multi-source context, and
the MCP server produces one complete, provenance-rich audit record rather than N
partial records requiring post-hoc correlation.

---

## IV. DETAILED DESCRIPTION

### A. System Architecture

The Compound Query Tier is implemented as middleware inside an MCP server process.
It does not require a separate server, a separate compute tier, or changes to the
MCP wire protocol. It is transparent to the calling agent except that compound tools
are registered alongside narrow tools in the MCP tool manifest.

```
┌──────────────────────────────────────────────────────────┐
│  AI Agent (any MCP-compatible runtime)                   │
└─────────────────────────┬────────────────────────────────┘
                          │ single MCP tool call
                          │ (compound or narrow)
┌─────────────────────────▼────────────────────────────────┐
│  MCP SERVER WITH COMPOUND QUERY TIER                     │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │ TOOL TYPE CLASSIFIER                             │   │
│  │   "narrow" → existing execution path            │   │
│  │   "compound" → Intent Router                    │   │
│  └──────────────────────┬───────────────────────────┘   │
│                         │ compound path only             │
│  ┌──────────────────────▼───────────────────────────┐   │
│  │ INTENT ROUTER                                    │   │
│  │   1. Load route from intent_routing_table        │   │
│  │      (cached in-process, TTL-refreshed)          │   │
│  │   2. Point-read materialized_intelligence_view   │   │
│  │      (single DB read — O(1) by entity key)       │   │
│  │   3. Optional: augment with vector search slice  │   │
│  │   4. Assemble result + source manifest           │   │
│  └──────────────────────┬───────────────────────────┘   │
│                         │                                │
│  ┌──────────────────────▼───────────────────────────┐   │
│  │ COMPOUND ATTESTATION RECORD WRITE                │   │
│  │   One record per compound call                   │   │
│  │   Includes: assembled_sources[], intent,         │   │
│  │             entity_key, result_hash              │   │
│  └──────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────┘
                          │
         assembled result returned to agent
```

### B. The Materialized Intelligence View

The materialized intelligence view is a database container where each document
represents the pre-joined context for a given entity (user, account, record, case,
or any domain entity). Documents are maintained by write-side triggers rather than
computed at query time.

**Document structure (generic):**

```json
{
  "id": "{entity_type}:{entity_id}",
  "entity_type": "account",
  "entity_id": "...",
  "domain": "...",
  "core_record": { ... },
  "related_records": [ ... ],
  "recent_events": [ ... ],
  "knowledge_hits": [
    {
      "citation": "...",
      "confidence": "HIGH | MEDIUM | LOW",
      "source_tier": 1,
      "last_verified": "..."
    }
  ],
  "last_refreshed": "2026-04-26T...",
  "knowledge_refresh_needed": 0
}
```

**Write-side refresh triggers (three patterns):**

1. **Change feed trigger:** Any write to the primary entity store fires a function
   that upserts the corresponding view document with the latest entity state.

2. **Knowledge ingest trigger:** Any knowledge base ingest run for a relevant domain
   sets a `knowledge_refresh_needed` flag on view documents in that domain. A
   background timer function refreshes `knowledge_hits` for flagged documents.

3. **Event ingest trigger:** Any new event for an entity appends to `recent_events`
   in the view document, trimmed to a configured window.

**Staleness handling:** If `last_refreshed` exceeds a configured threshold (e.g.,
24 hours), the Intent Router falls back to the narrow tool chain for that call and
queues a background refresh. The agent always receives a result; it never waits on
a stale view refresh.

### C. The Intent Routing Table

The intent routing table is a small configuration store, loaded at server cold start
and cached in-process with a TTL. It maps `(domain, intent)` pairs to query strategies.

```json
{
  "id": "{domain}:{intent}",
  "domain": "general",
  "intent": "full_context",
  "query_strategy": "materialized_view",
  "required_params": ["entity_id"],
  "optional_params": ["include_events", "include_knowledge", "knowledge_limit"],
  "defaults": { "include_events": true, "include_knowledge": true, "knowledge_limit": 5 },
  "cache_ttl_seconds": 300
}
```

Adding support for a new intent requires adding one route document — no code changes.

### D. Compound Tool Registration

Compound tools are registered in the MCP tool manifest alongside narrow tools.
From the agent's perspective, a compound tool is simply a tool with a well-defined
parameter schema. The agent does not know whether the tool is narrow or compound.

### E. Compound Attestation Record

One attestation record per compound call. SHA-256 hash of the result payload.
Full assembled_sources manifest capturing every data source contributing to the result.

```json
{
  "id": "{uuid}",
  "session_id": "...",
  "tool_name": "get_entity_context",
  "tool_type": "compound",
  "intent": "full_context",
  "domain": "general",
  "entity_id": "...",
  "assembled_sources": [
    "materialized_view::account:acct-001",
    "fts::kb-002",
    "fts::kb-006"
  ],
  "result_hash": "{sha256 of assembled result payload}",
  "timestamp": "2026-04-26T...",
  "latency_ms": 12
}
```

### F. Empirical Demonstration

The reference implementation at the URL above includes a formal parity test
(`tests/test_parity.py`) that demonstrates:

| Metric | Narrow chain (4 calls) | Compound call (1 call) |
|--------|----------------------|----------------------|
| Tool calls | 4 | 1 |
| Attestation records | 4 (must correlate by session_id) | 1 (complete provenance) |
| assembled_sources | None (each record partial) | Full manifest in one record |
| Data result | Equivalent | Equivalent |

The test `test_narrow_records_require_correlation_compound_does_not` formally
asserts this ratio and verifies data equivalence in a runnable test suite.

---

## V. CLAIMS OF NOVELTY (defensive publishing — not patent claims)

**1. Compound Query Tier inside MCP server middleware:**
The interception of MCP tool calls at the server middleware layer — before tool
execution — for the purpose of routing compound calls through a materialized view
lookup, as distinct from passing all calls through to individual tool implementations.

**2. Intent-to-query-strategy routing table for MCP:**
The use of a persistent, in-process-cached intent routing table inside an MCP server
to resolve agent-declared intent to a specific query strategy and materialized view
query, without requiring the agent to specify the join sequence.

**3. Materialized intelligence view maintained by write-side triggers, consumed
by MCP compound tools:**
The architectural pattern of maintaining a continuously-refreshed pre-joined view
document at the MCP server layer, updated by write-side event triggers from the
underlying data sources, such that compound MCP tool calls read a single pre-joined
document rather than querying N sources at call time.

**4. Single compound attestation record spanning multi-source assembled context:**
The generation of one attestation/audit record per compound MCP tool call that
captures the full set of source documents contributing to the assembled result
(the assembled_sources manifest), as distinct from N separate records that must
be correlated post-hoc.

**5. Staleness-triggered fallback from compound to narrow tool chain:**
The method of detecting view document staleness at compound call time and falling
back to the narrow tool chain for that call while queuing a background view refresh,
such that the agent always receives a result without waiting on stale data.

---

## VI. IMPLEMENTATION VARIANTS

**Variant A — Any database backend:** SQLite (reference impl), Cosmos DB, Postgres,
DynamoDB, or any document/relational/key-value store.

**Variant B — Any vector search backend:** SQLite FTS5 (reference impl), Azure AI
Search, Pinecone, Qdrant, or any semantic search service.

**Variant C — Stateless MCP servers:** Route cache externalized to Redis or similar
with the same TTL semantics.

**Variant D — Multi-tenant isolation:** Materialized view partition key includes
tenant_id. All queries scoped to calling agent's tenant.

**Variant E — Federated compound tools:** Multiple MCP servers, each owning a
different data domain, each implementing the Compound Query Tier independently.

---

## VII. WHAT THIS DISCLOSURE PREVENTS OTHERS FROM PATENTING

By publishing this disclosure, the following combinations enter the prior art and
cannot be the subject of a valid patent claim filed after this date:

- Materialized view lookup inside an MCP server middleware layer to collapse
  multi-step agent tool call chains into a single call
- Intent-to-query-strategy routing tables inside MCP servers
- Write-side trigger refresh of pre-joined view documents consumed by MCP tools
- Single compound attestation records with assembled_sources provenance manifests
  for MCP compound tool calls
- Staleness detection and narrow-tool fallback as a reliability pattern for
  materialized-view-backed MCP compound tools
- Any combination of the above in an MCP server regardless of the underlying
  database technology, agent runtime, or application domain

---

## VIII. RELATIONSHIP TO EXISTING WORK

This disclosure is inspired by the architectural insight that operating system kernels
can embed queryable data structures at the system layer to collapse application-level
orchestration. The translation of that insight to the MCP server layer — where the
server acts as the "kernel" for agent tool invocations — is the novel contribution.
No prior implementation of this pattern in MCP infrastructure is known to the author
as of the publication date.

---

_Published for defensive purposes. All rights reserved to the extent not precluded by
this publication. This document is intended to establish prior art and prevent
subsequent patent claims on the described methods and systems._

_Publication date: 2026-04-26_

---
---

# Defensive Publication II: Graph-Aware Vector Query Path for a Portable MCP Data Substrate

**Publication Date:** 2026-07-05
**Field:** Artificial Intelligence Infrastructure / Agent Retrieval / Knowledge Graphs
**Keywords:** MCP, vector search, knowledge graph, graph traversal, hybrid retrieval,
provenance, portable backend, embeddings abstraction, chain-of-custody
**Reference Implementation:** https://github.com/TechnologyOutlaws/mcp-db (tag v0.2.0)

---

## I. TECHNICAL FIELD

This disclosure extends the Compound Query Tier (Disclosure I) with a third,
co-resident integration path: a graph-aware vector query surface embedded in the same
MCP server, over the same pluggable backend. It is applicable to any AI agent runtime
that retrieves context over MCP and to any application wanting a directly queryable
vector/graph substrate behind the same tool surface.

---

## II. BACKGROUND

Agent builders face a fork: MCP tool-call ergonomics OR a directly queryable
vector/graph substrate — typically requiring separate systems, separate provenance
models, and a hard migration when moving between embedded (development) and managed
cloud (production) backends. Vector databases and graph databases are usually distinct
services; combining semantic recall with relationship traversal ordinarily means
wiring two systems and correlating their outputs in application code.

---

## III. SUMMARY OF THE DISCLOSURE

A single database-backed MCP server exposes three co-resident integration paths over
one pluggable, cloud-portable backend: (1) narrow point-read tools, (2) compound tools
returning pre-assembled multi-source context in a single call (Disclosure I), and (3) a
graph-aware vector query tool that combines semantic vector similarity with typed-edge
graph traversal to return a connected context subgraph. All three share one backend
abstraction implemented over embedded (SQLite) and managed cloud backends without
changing the tool surface. Each compound-path invocation emits one provenance record
enumerating every element assembled into the response.

---

## IV. DISCLOSED METHOD

1. **Pluggable backend abstraction** selected at runtime that implements both a
   record/point-read protocol and a graph/vector protocol comprising node upsert, edge
   upsert, vector similarity search, and depth-bounded typed-edge traversal with
   optional vector-similarity pruning of the traversal frontier. A backend may ship the
   record protocol without the graph protocol; the graph tool then reports the path is
   unavailable while the narrow/compound tools continue to function.
2. **Domain-neutral graph model** (node types: `entity`, `record`, `event`,
   `knowledge_chunk`; edge types: `relates_to`, `references`, `derived_from`, `cites`,
   `belongs_to`) that maps onto the same data already served by the point-read tools, so
   the graph is populated without a separate ingestion model.
3. **A single graph-query tool operable in two modes** — explicit-seed traversal, and
   vector-discovered-seed traversal — merging per-seed subgraphs into one connected
   result with traversal paths retained for provenance.
4. **A single provenance record per invocation** enumerating every node assembled into
   the response (the `assembled_sources` manifest), enabling chain-of-custody over an
   assembled subgraph rather than per element.
5. **A pluggable embeddings abstraction** that turns a text query intent into a query
   vector, with a dependency-free default provider (a deterministic hashing vectorizer)
   so the substrate runs fully offline with no model download or API key, and optional
   managed/local providers selected by configuration.
6. **A documented upgrade path** wherein the same backend abstraction and tool surface
   are wrapped by a compliance-hardening layer for regulated deployments, preserving the
   tool contract across the open and hardened variants.

---

## V. CLAIMS OF NOVELTY (defensive publishing — not patent claims)

1. A graph-aware vector query tool that seeds by semantic vector similarity and expands
   by typed-edge graph traversal within a single attested MCP tool call.
2. Two-mode seed selection (explicit seed node vs vector-discovered seeds) with per-seed
   subgraphs merged into one connected result inside an MCP server.
3. A single provenance record enumerating every node of an assembled subgraph for one
   MCP graph-query call.
4. A domain-neutral node/edge model populated from the same data served by the point-read
   tools, unifying three query paths over one backend.
5. A pluggable embeddings abstraction with a dependency-free default enabling offline
   operation of an MCP vector/graph substrate.

---

## VI. WHAT THIS DISCLOSURE PREVENTS OTHERS FROM PATENTING

By publishing this disclosure, the following combinations enter the prior art and
cannot be the subject of a valid patent claim filed after this date:

- Combining semantic vector seeding with typed-edge graph traversal in a single attested
  MCP tool call
- Two-mode (explicit vs vector-discovered seed) subgraph assembly merged into one MCP
  result
- A single provenance/attestation record enumerating every node of an assembled subgraph
- A domain-neutral graph model populated from the same data served by point-read MCP tools
- A pluggable embeddings abstraction enabling offline (dependency-free) operation of an
  MCP vector/graph substrate
- Any combination of the above across embedded and managed cloud backends without
  changing the MCP tool surface

---

## VII. PORTABILITY AND RELATIONSHIP TO EXISTING WORK

Reduced to practice over an embedded backend (SQLite with pure-Python cosine similarity
over stored vectors and adjacency tables). Implementable over managed backends providing
native or composed graph-plus-vector capability — e.g., document-store edges with a
native vector-distance query, a single engine unifying graph and vector, or a graph store
composed with a separate vector index. The tool surface is identical across backends.

---

## VIII. RESERVED — NOT DISCLOSED

This publication does not disclose, and Technology Outlaws LLC does not dedicate to the
public, the compliance-frame sealing mechanism, its attestation construction, or its
hardware-anchored trust layer, which are reserved and are the subject of separate,
non-public work. See [NOTICE.md](./NOTICE.md).

---

_Published for defensive purposes. All rights reserved to the extent not precluded by
this publication. This document is intended to establish prior art and prevent
subsequent patent claims on the described methods and systems._

_Publication date: 2026-07-05_
