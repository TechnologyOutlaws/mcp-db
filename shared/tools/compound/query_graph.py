"""
MCP-DB compound tool: query_graph — graph-aware vector query (integration path 3).

Combines semantic vector search with typed graph traversal in one call:

  * seed_node_id given  -> traverse the neighborhood around that node
  * seed_node_id None   -> vector_search picks the seed nodes, then traverse
                           each and merge the subgraphs

The query vector comes from an explicit ``query_vector`` (precomputed /
passthrough) or by embedding a text ``intent`` via the embeddings abstraction.
Writes ONE attestation record per call, listing every node touched
(``assembled_sources``) for provenance over the whole subgraph — the same
attestation contract as the other compound tools.

Backends that do not implement the graph/vector path raise
``GraphNotSupportedError`` (the narrow/compound view tools still work there).
"""

import time

from shared.attestation import Attestation
from shared.vector_graph import GraphNotSupportedError


async def query_graph(
    intent: str = "",
    query_vector: list[float] | None = None,
    seed_node_id: str | None = None,
    top_k: int = 5,
    depth: int = 1,
    edge_types: list[str] | None = None,
    node_type: str | None = None,
    vector_threshold: float = 0.0,
    domain: str = "general",
    session_id: str = "anonymous",
    db=None,
    embed=None,
) -> dict:
    """Return a connected subgraph assembled by vector similarity + traversal.

    Always returns a dict (never None). Empty intent + no seed + no query_vector
    yields an empty (but well-formed) result.
    """
    if db is None:
        from shared.db_factory import get_db

        db = get_db()

    if not hasattr(db, "graph_traverse"):
        import os

        raise GraphNotSupportedError(os.environ.get("DB_VARIANT", "sqlite"))

    attestation = Attestation(db=db)
    t0 = time.monotonic()

    # Resolve a query vector: an explicit precomputed vector wins; otherwise
    # embed the text intent via the configured embedder.
    if query_vector is None and intent:
        if embed is None:
            from shared.embeddings import get_embedder

            embed = get_embedder()
        query_vector = await embed(intent)

    vector_hits: list[dict] = []
    if query_vector is not None:
        filters = {"node_type": node_type} if node_type else None
        vector_hits = await db.vector_search(
            query_vector, top_k=top_k, filters=filters
        )
        if vector_threshold:
            vector_hits = [
                h for h in vector_hits
                if h.get("score", 0.0) >= vector_threshold
            ]

    # Seed selection: explicit seed vs vector-discovered seeds.
    if seed_node_id:
        seeds = [seed_node_id]
    else:
        seeds = [h["node_id"] for h in vector_hits]

    merged_nodes: dict[str, dict] = {}
    merged_edges: dict[str, dict] = {}
    paths: list[dict] = []
    for seed in seeds:
        sub = await db.graph_traverse(seed, depth=depth, edge_types=edge_types)
        for node in sub["nodes"]:
            merged_nodes[node["node_id"]] = node
        for edge in sub["edges"]:
            ekey = f"{edge['source_id']}|{edge['edge_type']}|{edge['target_id']}"
            merged_edges[ekey] = edge
            paths.append(
                {
                    "from": edge["source_id"],
                    "edge": edge["edge_type"],
                    "to": edge["target_id"],
                    "seed": seed,
                }
            )

    nodes = list(merged_nodes.values())
    edges = list(merged_edges.values())
    subgraph = {"nodes": nodes, "edges": edges}

    # Provenance: vector hits + every node reached by traversal (deduped, ordered).
    seen: set[str] = set()
    assembled_sources: list[str] = []
    for hit in vector_hits:
        key = f"vector::{hit['node_id']}"
        if key not in seen:
            seen.add(key)
            assembled_sources.append(key)
    if seed_node_id:
        key = f"graph::{seed_node_id}"
        if key not in seen:
            seen.add(key)
            assembled_sources.append(key)
    for node in nodes:
        key = f"graph::{node['node_id']}"
        if key not in seen:
            seen.add(key)
            assembled_sources.append(key)

    latency_ms = int((time.monotonic() - t0) * 1000)

    result = {
        "intent": intent,
        "vector_hits": vector_hits,
        "subgraph": subgraph,
        "nodes": nodes,
        "edges": edges,
        "paths": paths,
        "assembled_sources": assembled_sources,
    }

    entity_id = seed_node_id or (vector_hits[0]["node_id"] if vector_hits else "")
    record_id = await attestation.write(
        session_id=session_id,
        tool_name="query_graph",
        intent=intent or "vector_graph",
        domain=domain,
        entity_id=entity_id,
        assembled_sources=assembled_sources,
        result_payload=result,
        latency_ms=latency_ms,
        tool_type="compound",
    )

    result["attestation_record_id"] = record_id
    return result
