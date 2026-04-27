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

CONTAINER_VIEW = "materialized_intelligence_view"
CONTAINER_ROUTES = "intent_routing_table"
CONTAINER_ATTESTATION = "compound_attestation_log"
CONTAINER_KNOWLEDGE = "knowledge_base"


class CosmosDB:

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

    async def close(self) -> None:
        await self._client.close()
        await self._credential.close()
