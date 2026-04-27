"""
MCP-DB compound tool: search_knowledge
Attested knowledge base search. No entity context required.
Writes ONE attestation record per call.
"""

import time
from shared.attestation import Attestation


async def search_knowledge(
    query: str,
    top: int = 5,
    tier_min: int = 1,
    domain: str = "general",
    session_id: str = "anonymous",
    db=None,
) -> dict:
    if db is None:
        from shared.db_factory import get_db

        db = get_db()

    attestation = Attestation(db=db)

    t0 = time.monotonic()
    hits = await db.search_knowledge(query=query, top=top, tier_min=tier_min)
    latency_ms = int((time.monotonic() - t0) * 1000)

    assembled_sources = [f"fts::{h['id']}" for h in hits]
    result = {
        "hits": hits,
        "assembled_sources": assembled_sources,
    }

    record_id = await attestation.write(
        session_id=session_id,
        tool_name="search_knowledge",
        intent="knowledge_search",
        domain=domain,
        entity_id="",
        assembled_sources=assembled_sources,
        result_payload=result,
        latency_ms=latency_ms,
        tool_type="compound",
    )

    result["attestation_record_id"] = record_id
    return result
