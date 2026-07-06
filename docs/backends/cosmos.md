# Backend Spec — Azure Cosmos DB for NoSQL (`DB_VARIANT=cosmos`)

Implements the graph/vector protocol on Azure Cosmos DB for NoSQL using
`vectorEmbeddingPolicy` + `VectorDistance()` for similarity and edge documents
traversed in application code for the graph. Auth is `DefaultAzureCredential`
only — no connection strings, no keys (see CLAUDE.md).

## Platform constraints (verify live before coding)

- **The vector policy is set at container creation and CANNOT be added to an
  existing container.** A new vector-enabled container is required — never
  retrofit an existing one.
- The account capability **`EnableNoSQLVectorSearch`** must be enabled first
  (one-way, account-wide; `az cosmosdb update --capabilities EnableNoSQLVectorSearch`).
- The flat vector index caps around 505 dimensions → use `quantizedFlat` or
  `DiskANN` for 1536-dim embeddings.

## Containers

| Container | Partition key | Vector | Notes |
|---|---|---|---|
| `mcp_nodes` | `/node_type` | `vectorEmbeddingPolicy` on `/embedding`, cosine, `EMBED_DIM` dims, `quantizedFlat`/`DiskANN` index | one document per node |
| `mcp_edges` | `/source_id` | none | plain edge documents |

Provision via the control plane (ARM / `az` / Bicep), not the data-plane SDK —
container creation cannot be authorized by an AAD token on the data plane.

## Method mapping

- `upsert_node` → upsert `{id, node_id, node_type, properties, embedding}` into
  `mcp_nodes`.
- `upsert_edge` → upsert `{id: "{source}|{edge_type}|{target}", source_id,
  target_id, edge_type, weight}` into `mcp_edges`.
- `vector_search` → `SELECT TOP @k c.node_id, c.node_type, c.properties,
  VectorDistance(c.embedding, @vec) AS score FROM c [WHERE c.node_type=@t]
  ORDER BY VectorDistance(c.embedding, @vec)`.
- `graph_traverse` → application-side BFS: read edges by `source_id`, expand the
  frontier one hop per depth level, batch-read frontier nodes. Bound frontier
  size to avoid RU blow-ups.

## Done conditions

- [ ] `DB_VARIANT=cosmos` returns a backend implementing all four graph methods.
- [ ] `mcp_nodes` / `mcp_edges` provisioned with the vector policy (documented
      `az`/ARM commands); no throughput passed on serverless accounts.
- [ ] `query_graph` returns identical shape to the SQLite backend against a seeded
      account (integration test gated behind an env flag; unit tests mock the
      Cosmos client).
- [ ] No hardcoded endpoints/keys; `DefaultAzureCredential` only.
- [ ] Existing narrow/compound tests unaffected; full suite green.
