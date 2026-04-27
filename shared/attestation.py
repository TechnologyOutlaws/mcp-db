"""
MCP-DB — Attestation record writer.
Generates one tamper-evident attestation record per compound tool call.
SHA-256 hashes the result payload for integrity verification.
"""

import hashlib
import json
import uuid
from datetime import datetime, timezone


class Attestation:

    def __init__(self, db):
        self._db = db

    async def write(
        self,
        session_id: str,
        tool_name: str,
        intent: str,
        domain: str,
        entity_id: str,
        assembled_sources: list[str],
        result_payload: dict,
        latency_ms: int,
        tool_type: str = "compound",
    ) -> str:
        record_id = str(uuid.uuid4())
        result_hash = hashlib.sha256(
            json.dumps(result_payload, sort_keys=True).encode()
        ).hexdigest()

        record = {
            "id": record_id,
            "session_id": session_id,
            "tool_name": tool_name,
            "tool_type": tool_type,
            "intent": intent,
            "domain": domain,
            "entity_id": entity_id,
            "assembled_sources": json.dumps(assembled_sources),
            "result_hash": result_hash,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "latency_ms": latency_ms,
        }

        await self._db.write_attestation(record)
        return record_id
