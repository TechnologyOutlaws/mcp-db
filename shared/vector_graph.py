"""
MCP-DB — Vector-Graph abstraction base.

Defines the contract for a backend that supports both vector (embedding)
similarity search and graph traversal over the same node/edge store. Both
the SQLite (offline, pure-Python) and Cosmos (cloud) backends implement it.

This extends the Compound Query Tier: the materialized view collapses an
entity's pre-joined context, and the vector-graph layer adds semantic recall
(vector_search) plus relationship expansion (graph_traverse) over a node/edge
store — assembled by a single compound tool (query_graph) into one attested
result.

Contract (all async):
  vector_search(query_vector, top_k, filters) -> list[dict]
      Rank nodes by similarity to query_vector. Each result dict carries at
      least: node_id, node_type, properties, score.
  graph_traverse(start_node_id, depth, edge_types) -> dict
      BFS from start_node_id out to `depth` hops, optionally restricted to
      edge_types. Returns {"nodes": [...], "edges": [...]}; the start node is
      excluded from "nodes" (only reached nodes are returned).
  upsert_node(node_id, node_type, properties, embedding) -> None
  upsert_edge(source_id, target_id, edge_type, weight) -> None
"""

from abc import ABC, abstractmethod


class VectorGraphDB(ABC):

    @abstractmethod
    async def vector_search(
        self,
        query_vector: list[float],
        top_k: int = 5,
        filters: dict | None = None,
    ) -> list[dict]:
        """Return up to top_k nodes ranked by similarity to query_vector."""
        raise NotImplementedError

    @abstractmethod
    async def graph_traverse(
        self,
        start_node_id: str,
        depth: int = 1,
        edge_types: list[str] | None = None,
    ) -> dict:
        """BFS from start_node_id to `depth` hops; returns nodes + edges."""
        raise NotImplementedError

    @abstractmethod
    async def upsert_node(
        self,
        node_id: str,
        node_type: str,
        properties: dict,
        embedding: list[float],
    ) -> None:
        """Insert or replace a node with its embedding."""
        raise NotImplementedError

    @abstractmethod
    async def upsert_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str,
        weight: float = 1.0,
    ) -> None:
        """Insert or replace a directed edge between two nodes."""
        raise NotImplementedError
