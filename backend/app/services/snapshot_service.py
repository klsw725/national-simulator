from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from app.clients.shadowbroker import BBox, ShadowBrokerClient
from app.database import get_pool


class SnapshotService:
    def __init__(self, sb_client: ShadowBrokerClient):
        self.sb = sb_client

    async def create_snapshot(
        self, scenario_id: str, bbox: list[float] | None = None,
    ) -> dict[str, Any]:
        sb_bbox = BBox(s=bbox[1], w=bbox[0], n=bbox[3], e=bbox[2]) if bbox and len(bbox) >= 4 else None

        fast_data = await self.sb.get_fast_data(sb_bbox)
        slow_data = await self.sb.get_slow_data(sb_bbox)

        snapshot_id = f"snap_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()

        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO scenario_snapshots (id, scenario_id, fast_data, slow_data, snapshot_at, created_at)
                   VALUES ($1, $2, $3, $4, $5, $6)
                   ON CONFLICT DO NOTHING""",
                snapshot_id,
                scenario_id,
                json.dumps(fast_data, ensure_ascii=False),
                json.dumps(slow_data, ensure_ascii=False),
                now,
                now,
            )

        return {
            "snapshot_id": snapshot_id,
            "scenario_id": scenario_id,
            "snapshot_at": now,
            "fast_sources": len(fast_data) if isinstance(fast_data, dict) else 0,
            "slow_sources": len(slow_data) if isinstance(slow_data, dict) else 0,
        }

    async def get_snapshot(self, scenario_id: str) -> dict[str, Any] | None:
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM scenario_snapshots WHERE scenario_id = $1 ORDER BY created_at DESC LIMIT 1",
                scenario_id,
            )
        if not row:
            return None
        return {
            "id": row["id"],
            "scenario_id": row["scenario_id"],
            "fast_data": json.loads(row["fast_data"]) if row["fast_data"] else {},
            "slow_data": json.loads(row["slow_data"]) if row["slow_data"] else {},
            "snapshot_at": row["snapshot_at"],
        }

    async def get_snapshot_metadata(self, scenario_id: str) -> dict[str, Any] | None:
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, scenario_id, snapshot_at, created_at, length(fast_data) as fast_size, length(slow_data) as slow_size FROM scenario_snapshots WHERE scenario_id = $1 ORDER BY created_at DESC LIMIT 1",
                scenario_id,
            )
        if not row:
            return None
        return {
            "id": row["id"],
            "scenario_id": row["scenario_id"],
            "snapshot_at": row["snapshot_at"],
            "fast_data_size_bytes": row["fast_size"] or 0,
            "slow_data_size_bytes": row["slow_size"] or 0,
        }
