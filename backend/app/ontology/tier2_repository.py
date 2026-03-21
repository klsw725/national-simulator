from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from app.database import get_pool
from app.ontology.validator import StixValidator


class Tier2Repository:
    def __init__(self):
        self._validator = StixValidator()

    async def create(
        self,
        object_type: str,
        properties: dict[str, Any],
        source: str = "",
        confidence: float = 0.0,
        branch_id: str | None = None,
    ) -> dict[str, Any]:
        stix_obj = self._validator.validate(object_type, properties)
        stix_json = self._validator.serialize(stix_obj)
        stix_id = stix_obj.id

        row_id = f"stix_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()

        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO stix_objects (id, stix_id, object_type, stix_json, confidence, source, branch_id, created_at, updated_at)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                   ON CONFLICT (stix_id) DO UPDATE SET stix_json = $4, confidence = $5, branch_id = $7, updated_at = $9""",
                row_id,
                stix_id,
                object_type,
                stix_json,
                confidence,
                source,
                branch_id,
                now,
                now,
            )

        return {
            "id": row_id,
            "stix_id": stix_id,
            "object_type": object_type,
            "stix_json": json.loads(stix_json),
            "branch_id": branch_id,
        }

    async def get_by_stix_id(self, stix_id: str) -> dict[str, Any] | None:
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM stix_objects WHERE stix_id = $1", stix_id)
        if not row:
            return None
        return self._row_to_dict(row)

    async def list_by_type(
        self,
        object_type: str,
        limit: int = 100,
        offset: int = 0,
        branch_id: str | None = None,
    ) -> list[dict[str, Any]]:
        pool = get_pool()
        async with pool.acquire() as conn:
            if branch_id:
                rows = await conn.fetch(
                    "SELECT * FROM stix_objects WHERE object_type = $1 AND branch_id = $2 ORDER BY created_at DESC LIMIT $3 OFFSET $4",
                    object_type,
                    branch_id,
                    limit,
                    offset,
                )
            else:
                rows = await conn.fetch(
                    "SELECT * FROM stix_objects WHERE object_type = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3",
                    object_type,
                    limit,
                    offset,
                )
        return [self._row_to_dict(row) for row in rows]

    async def delete(self, stix_id: str) -> bool:
        pool = get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute("DELETE FROM stix_objects WHERE stix_id = $1", stix_id)
        return result != "DELETE 0"

    def _row_to_dict(self, row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "stix_id": row["stix_id"],
            "object_type": row["object_type"],
            "stix_json": json.loads(row["stix_json"]),
            "confidence": row["confidence"],
            "source": row["source"],
            "branch_id": row["branch_id"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
