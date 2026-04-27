"""
MCP-DB narrow tool: get_entity
Returns the core record for a single entity.
Writes one attestation record (tool_type="narrow").
"""

import json
import time
from shared.attestation import Attestation


async def get_entity(
    entity_id: str,
    entity_type: str = "account",
    session_id: str = "anonymous",
    db=None,
) -> dict | None:
    if db is None:
        from shared.db_factory import get_db

        db = get_db()

    t0 = time.monotonic()
    view = await db.get_materialized_view(entity_id, entity_type)
    latency_ms = int((time.monotonic() - t0) * 1000)

    if view is None:
        return None

    entity = json.loads(view["core_record"])
    result = {"entity": entity}

    attestation = Attestation(db=db)
    record_id = await attestation.write(
        session_id=session_id,
        tool_name="get_entity",
        intent="narrow",
        domain=view.get("domain", "general"),
        entity_id=entity_id,
        assembled_sources=[f"materialized_view::{view['id']}"],
        result_payload=result,
        latency_ms=latency_ms,
        tool_type="narrow",
    )
    result["attestation_record_id"] = record_id
    return result
