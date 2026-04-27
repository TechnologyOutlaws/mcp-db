"""
MCP-DB narrow tool: get_knowledge_hits
FTS search over knowledge_base. No entity context required.
Writes one attestation record (tool_type="narrow").
"""

import time
from shared.attestation import Attestation


async def get_knowledge_hits(
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

    t0 = time.monotonic()
    hits = await db.search_knowledge(query=query, top=top, tier_min=tier_min)
    latency_ms = int((time.monotonic() - t0) * 1000)

    result = {"hits": hits}
    assembled_sources = [f"fts::{h['id']}" for h in hits]

    attestation = Attestation(db=db)
    record_id = await attestation.write(
        session_id=session_id,
        tool_name="get_knowledge_hits",
        intent="narrow",
        domain=domain,
        entity_id="",
        assembled_sources=assembled_sources,
        result_payload=result,
        latency_ms=latency_ms,
        tool_type="narrow",
    )
    result["attestation_record_id"] = record_id
    return result
