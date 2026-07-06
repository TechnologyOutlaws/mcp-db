# Backend Spec — AWS Neptune (`DB_VARIANT=aws`)

Graph store and vector index are separate Neptune surfaces: the property graph
lives in Neptune (openCypher/Gremlin); vectors live in Neptune Analytics' vector
index or, where unavailable, OpenSearch k-NN keyed by `node_id`. This backend
composes the two — the most surface-area of the four, so verify the current
Neptune Analytics vector API live before coding.

## Platform notes (verify live before coding)

- Neptune Analytics vector API availability varies by region — confirm current
  API/limits before implementing; fall back to OpenSearch k-NN if absent.
- Auth via AWS SigV4 with an IAM role — no static keys in code.

## Method mapping

- `upsert_node` → openCypher `MERGE` on the node with its properties; write the
  embedding to the vector index (Neptune Analytics or OpenSearch) keyed by
  `node_id`.
- `upsert_edge` → openCypher `MERGE` on the typed relationship with `weight`.
- `vector_search` → query the vector index for nearest `node_id`s, then read node
  properties from the graph; return `node_id, node_type, properties, score`.
- `graph_traverse` → openCypher variable-length path bounded by `depth`
  (`MATCH p=(s)-[:TYPE*1..depth]->(n)`), edge-type filtered; when a query
  embedding + threshold are supplied, intersect the traversal frontier with the
  vector-index results.

## Done conditions

- [ ] `DB_VARIANT=aws` returns a backend implementing all four graph methods.
- [ ] Vector store selection (Neptune Analytics vs OpenSearch k-NN) is
      configurable and documented.
- [ ] `query_graph` returns identical shape to the SQLite backend against a seeded
      cluster (integration test gated behind an env flag; unit tests mock the
      clients).
- [ ] IAM/SigV4 auth only; no static keys in code.
- [ ] Existing narrow/compound tests unaffected; full suite green.
