# Backend Implementation Specs

`mcp-db` selects a backend at runtime via `DB_VARIANT`. Every backend implements
the record/point-read protocol; graph-capable backends also implement the
graph/vector protocol (`shared/vector_graph.py`: `upsert_node`, `upsert_edge`,
`vector_search`, `graph_traverse`). A backend without the graph path raises
`GraphNotSupportedError` — the narrow/compound tools still work; only
`query_graph` is unavailable.

These specs are the build plan for the remaining cloud backends. Each is a
standalone unit of work: implement one backend, keep the tool surface unchanged,
add its tests, verify green.

| `DB_VARIANT` | Backend | Status | Spec |
|---|---|---|---|
| `sqlite` | SQLite (pure-Python cosine + adjacency) | **shipped** (default, CI) | — |
| `cosmos` | Azure Cosmos DB for NoSQL | vector-graph implemented; see spec for the dedicated vector-container hardening | [cosmos.md](./cosmos.md) |
| `gcp` | GCP Spanner Graph (native GQL + ScaNN) | planned | [spanner.md](./spanner.md) |
| `aws` | AWS Neptune (openCypher + vector index) | planned | [neptune.md](./neptune.md) |

## Conformance rules (all backends)

1. **Same tool surface.** The abstract interface hides backend differences from
   the tools entirely. `query_graph` must behave identically regardless of
   `DB_VARIANT`.
2. **Interface contract.** `vector_search(query_vector, top_k, filters)` returns
   nodes ranked by similarity, each carrying `node_id, node_type, properties,
   score`. `graph_traverse(start_node_id, depth, edge_types)` returns
   `{nodes, edges}`, start node excluded from `nodes`.
3. **Domain-neutral model.** Node types `entity | record | event |
   knowledge_chunk`; edge types `relates_to | references | derived_from | cites |
   belongs_to`. No domain semantics in this repo.
4. **Embeddings.** Dimension is `EMBED_DIM`; the query embedder is pluggable
   (`shared/embeddings.py`). Stored node vectors and query vectors must share a
   dimension.
5. **Attestation.** One record per `query_graph` call, `assembled_sources`
   enumerating every node touched.
6. **Secrets / auth.** No hardcoded endpoints or keys. Cloud backends use the
   platform's managed identity where available.
