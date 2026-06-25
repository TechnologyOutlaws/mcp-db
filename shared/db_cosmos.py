"""
MCP-DB — Cosmos DB abstraction layer.
Cloud variant. DefaultAzureCredential only — no connection strings (SD-07).
Requires env vars: COSMOS_ENDPOINT, COSMOS_DATABASE.

Interface identical to db_sqlite.py.
"""

import os

from azure.cosmos.aio import CosmosClient
from azure.identity.aio import DefaultAzureCredential
from azure.core.exceptions import ResourceNotFoundError

from shared.vector_graph import VectorGraphDB

CONTAINER_VIEW = "materialized_intelligence_view"
CONTAINER_ROUTES = "intent_routing_table"
CONTAINER_ATTESTATION = "compound_attestation_log"
CONTAINER_KNOWLEDGE = "knowledge_base"
CONTAINER_GRAPH_NODE = "graph_node"
CONTAINER_GRAPH_EDGE = "graph_edge"


class CosmosDB(VectorGraphDB):

    def __init__(
        self,
        endpoint: str | None = None,
        database: str | None = None,
    ):
        self.endpoint = endpoint or os.environ["COSMOS_ENDPOINT"]
        self.database = database or os.environ["COSMOS_DATABASE"]
        self._credential = DefaultAzureCredential()
        self._client = CosmosClient(self.endpoint, credential=self._credential)
        self._db = self._client.get_database_client(self.database)

    def _container(self, name: str):
        return self._db.get_container_client(name)

    async def get_materialized_view(
        self, entity_id: str, entity_type: str
    ) -> dict | None:
        view_id = f"general:{entity_type}:{entity_id}"
        try:
            return await self._container(CONTAINER_VIEW).read_item(
                item=view_id, partition_key="general"
            )
        except ResourceNotFoundError:
            return None

    async def get_route(self, domain: str, intent: str) -> dict | None:
        route_id = f"{domain}:{intent}"
        try:
            return await self._container(CONTAINER_ROUTES).read_item(
                item=route_id, partition_key=domain
            )
        except ResourceNotFoundError:
            return None

    async def search_knowledge(
        self, query: str, top: int = 5, tier_min: int = 1
    ) -> list[dict]:
        sql = (
            "SELECT TOP @top c.id, c.domain, c.content, c.citation, "
            "c.confidence, c.source_tier, c.last_verified "
            "FROM c WHERE CONTAINS(c.content, @query) "
            "AND c.source_tier >= @tier_min"
        )
        params = [
            {"name": "@top", "value": top},
            {"name": "@query", "value": query},
            {"name": "@tier_min", "value": tier_min},
        ]
        items = []
        async for item in self._container(CONTAINER_KNOWLEDGE).query_items(
            query=sql, parameters=params
        ):
            items.append(item)
        return items

    async def write_attestation(self, record: dict) -> None:
        await self._container(CONTAINER_ATTESTATION).upsert_item(record)

    async def get_attestation(self, record_id: str) -> dict | None:
        try:
            return await self._container(CONTAINER_ATTESTATION).read_item(
                item=record_id, partition_key=record_id
            )
        except ResourceNotFoundError:
            return None

    async def upsert_materialized_view(self, doc: dict) -> None:
        await self._container(CONTAINER_VIEW).upsert_item(doc)

    async def get_stale_views(self) -> list[dict]:
        sql = "SELECT * FROM c WHERE c.knowledge_refresh_needed = 1"
        items = []
        async for item in self._container(CONTAINER_VIEW).query_items(
            query=sql
        ):
            items.append(item)
        return items

    # ── Vector-Graph methods (VectorGraphDB) ──────────────────────────
    #
    # Cosmos NoSQL native vector search via VectorDistance() ORDER BY, which
    # requires a vector indexing policy on the graph_node container's
    # /embedding path (provisioned out-of-band, same as the existing
    # containers). graph_traverse walks the graph_edge container with a
    # bounded BFS, one query per frontier hop — mirroring how the existing
    # methods issue query_items / read_item against their containers.

    async def upsert_node(
        self,
        node_id: str,
        node_type: str,
        properties: dict,
        embedding: list[float],
    ) -> None:
        doc = {
            "id": node_id,
            "node_id": node_id,
            "node_type": node_type,
            "properties": properties or {},
            "embedding": embedding or [],
        }
        await self._container(CONTAINER_GRAPH_NODE).upsert_item(doc)

    async def upsert_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str,
        weight: float = 1.0,
    ) -> None:
        edge_id = f"{source_id}|{edge_type}|{target_id}"
        doc = {
            "id": edge_id,
            "source_id": source_id,
            "target_id": target_id,
            "edge_type": edge_type,
            "weight": weight,
        }
        await self._container(CONTAINER_GRAPH_EDGE).upsert_item(doc)

    async def vector_search(
        self,
        query_vector: list[float],
        top_k: int = 5,
        filters: dict | None = None,
    ) -> list[dict]:
        filters = filters or {}
        where = ""
        params = [
            {"name": "@vec", "value": query_vector},
            {"name": "@top", "value": top_k},
        ]
        if "node_type" in filters:
            where = "WHERE c.node_type = @node_type "
            params.append(
                {"name": "@node_type", "value": filters["node_type"]}
            )

        sql = (
            "SELECT TOP @top c.node_id, c.node_type, c.properties, "
            "VectorDistance(c.embedding, @vec) AS score "
            f"FROM c {where}"
            "ORDER BY VectorDistance(c.embedding, @vec)"
        )
        results = []
        async for item in self._container(CONTAINER_GRAPH_NODE).query_items(
            query=sql, parameters=params
        ):
            results.append(item)
        return results

    async def graph_traverse(
        self,
        start_node_id: str,
        depth: int = 1,
        edge_types: list[str] | None = None,
    ) -> dict:
        try:
            await self._container(CONTAINER_GRAPH_NODE).read_item(
                item=start_node_id, partition_key=start_node_id
            )
        except ResourceNotFoundError:
            return {"nodes": [], "edges": []}

        visited = {start_node_id}
        frontier = [start_node_id]
        reached_edges: list[dict] = []
        edge_container = self._container(CONTAINER_GRAPH_EDGE)

        for _ in range(max(0, depth)):
            if not frontier:
                break
            sql = "SELECT * FROM c WHERE ARRAY_CONTAINS(@frontier, c.source_id)"
            params = [{"name": "@frontier", "value": frontier}]
            if edge_types:
                sql += " AND ARRAY_CONTAINS(@edge_types, c.edge_type)"
                params.append({"name": "@edge_types", "value": edge_types})

            next_frontier = []
            async for edge in edge_container.query_items(
                query=sql, parameters=params
            ):
                reached_edges.append(
                    {
                        "source_id": edge["source_id"],
                        "target_id": edge["target_id"],
                        "edge_type": edge["edge_type"],
                        "weight": edge.get("weight", 1.0),
                    }
                )
                tgt = edge["target_id"]
                if tgt not in visited:
                    visited.add(tgt)
                    next_frontier.append(tgt)
            frontier = next_frontier

        reached_ids = [nid for nid in visited if nid != start_node_id]
        nodes: list[dict] = []
        if reached_ids:
            sql = (
                "SELECT c.node_id, c.node_type, c.properties FROM c "
                "WHERE ARRAY_CONTAINS(@ids, c.node_id)"
            )
            params = [{"name": "@ids", "value": reached_ids}]
            async for node in self._container(
                CONTAINER_GRAPH_NODE
            ).query_items(query=sql, parameters=params):
                nodes.append(node)

        return {"nodes": nodes, "edges": reached_edges}

    async def close(self) -> None:
        await self._client.close()
        await self._credential.close()
