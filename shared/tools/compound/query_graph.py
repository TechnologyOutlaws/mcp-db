"""
MCP-DB compound tool: query_graph

Vector-graph compound tool. Single call: (1) vector_search to find the most
semantically similar seed node(s), then (2) graph_traverse to expand the
neighborhood around the top seed out to `depth` hops, optionally filtered by
edge_types. Returns the assembled vector hits + subgraph and writes ONE
attestation record covering every source contributing to the result.

Mirrors get_entity_context.py: one compound call -> one attestation record ->
assembled multi-source result, vs. N narrow vector/graph calls.
"""

import time
from shared.attestation import Attestation


async def query_graph(
    query_vector: list[float],
    top_k: int = 5,
    depth: int = 1,
    edge_types: list[str] | None = None,
    node_type: str | None = None,
    domain: str = "general",
    session_id: str = "anonymous",
    db=None,
) -> dict:
    if db is None:
        from shared.db_factory import get_db

        db = get_db()

    attestation = Attestation(db=db)

    t0 = time.monotonic()

    filters = {"node_type": node_type} if node_type else None
    vector_hits = await db.vector_search(
        query_vector, top_k=top_k, filters=filters
    )

    subgraph = {"nodes": [], "edges": []}
    if vector_hits:
        seed_id = vector_hits[0]["node_id"]
        subgraph = await db.graph_traverse(
            seed_id, depth=depth, edge_types=edge_types
        )

    latency_ms = int((time.monotonic() - t0) * 1000)

    assembled_sources = [f"vector::{h['node_id']}" for h in vector_hits]
    assembled_sources += [
        f"graph::{n['node_id']}" for n in subgraph["nodes"]
    ]

    result = {
        "vector_hits": vector_hits,
        "subgraph": subgraph,
        "assembled_sources": assembled_sources,
    }

    record_id = await attestation.write(
        session_id=session_id,
        tool_name="query_graph",
        intent="vector_graph",
        domain=domain,
        entity_id=vector_hits[0]["node_id"] if vector_hits else "",
        assembled_sources=assembled_sources,
        result_payload=result,
        latency_ms=latency_ms,
        tool_type="compound",
    )

    result["attestation_record_id"] = record_id
    return result
