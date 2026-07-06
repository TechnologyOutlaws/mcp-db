# Backend Spec — GCP Spanner Graph (`DB_VARIANT=gcp`)

The cleanest native fit: Spanner (Enterprise edition) does graph + vector +
relational in one engine, so `graph_traverse` needs no application-side BFS — the
engine executes the path pattern with vector distance in the same query.

## Platform notes (verify live before coding)

- Requires Spanner **Enterprise edition** for native Spanner Graph (ISO GQL) and
  the ScaNN ANN vector index.
- **Spanner Omni** (containerized) runs on Azure / AWS / on-prem — the multi-cloud
  escape hatch, worth noting for portability.
- Auth via Application Default Credentials (ADC) — no keys in code.

## Schema

- `nodes(node_id STRING PK, node_type STRING, properties JSON,
  embedding ARRAY<FLOAT32>(vector_length=>EMBED_DIM), created_at TIMESTAMP)`.
- `edges(source_id, target_id, edge_type, weight, PK(source_id,target_id,edge_type))`.
- A Spanner Graph defined over `nodes`/`edges` as a property graph (node table +
  edge table mapped to a `PROPERTY GRAPH`).
- ScaNN vector index on `nodes.embedding` for ANN; exact KNN for small sets.

## Method mapping

- `upsert_node` / `upsert_edge` → `INSERT OR UPDATE` (mutations) on the tables.
- `vector_search` → `APPROX_COSINE_DISTANCE` with the ScaNN index (ANN), or
  `COSINE_DISTANCE` (exact KNN) for small sets; `ORDER BY` distance, `LIMIT @k`.
- `graph_traverse` → native GQL `MATCH` path pattern bounded by `depth`, with the
  vector distance available in the same query; no application-side BFS.

## Done conditions

- [ ] `DB_VARIANT=gcp` returns a backend implementing all four graph methods.
- [ ] `query_graph` returns identical shape to the SQLite backend against a seeded
      instance (integration test gated behind an env flag; unit tests mock the
      Spanner client).
- [ ] ADC only; no keys in code; edition/index requirements documented.
- [ ] Existing narrow/compound tests unaffected; full suite green.
