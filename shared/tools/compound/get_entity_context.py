"""
MCP-DB compound tool: get_entity_context
The primary compound tool. Single call returns assembled entity context.
Delegates to IntentRouter. Writes ONE attestation record.

This is the tool that demonstrates the Compound Query Tier pattern:
  one call -> one attestation record -> assembled multi-source result
vs. four narrow calls -> four attestation records -> same data.
"""

import time
from shared.intent_router import IntentRouter
from shared.attestation import Attestation


async def get_entity_context(
    entity_id: str,
    entity_type: str = "account",
    intent: str = "full_context",
    domain: str = "general",
    include_knowledge: bool = True,
    knowledge_limit: int = 5,
    include_events: bool = True,
    session_id: str = "anonymous",
    db=None,
) -> dict | None:
    if db is None:
        from shared.db_factory import get_db

        db = get_db()

    router = IntentRouter(db=db)
    attestation = Attestation(db=db)

    t0 = time.monotonic()
    result = await router.resolve(
        entity_id=entity_id,
        entity_type=entity_type,
        intent=intent,
        domain=domain,
        include_knowledge=include_knowledge,
        knowledge_limit=knowledge_limit,
        include_events=include_events,
    )
    latency_ms = int((time.monotonic() - t0) * 1000)

    if result is None:
        return None

    record_id = await attestation.write(
        session_id=session_id,
        tool_name="get_entity_context",
        intent=intent,
        domain=domain,
        entity_id=entity_id,
        assembled_sources=result["assembled_sources"],
        result_payload=result,
        latency_ms=latency_ms,
        tool_type="compound",
    )

    result["attestation_record_id"] = record_id
    return result
