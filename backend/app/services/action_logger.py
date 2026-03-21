from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from app.database import get_pool


class ActionLogger:
    @staticmethod
    async def log(
        action_type: str,
        scenario_id: str | None = None,
        actor: str = "system",
        payload: dict[str, Any] | None = None,
    ) -> str:
        action_id = f"act_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO action_log (id, scenario_id, action_type, actor, payload, created_at) VALUES ($1, $2, $3, $4, $5, $6)",
                action_id,
                scenario_id,
                action_type,
                actor,
                json.dumps(payload, ensure_ascii=False) if payload else None,
                now,
            )
        return action_id

    @staticmethod
    async def query(
        scenario_id: str | None = None,
        action_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        pool = get_pool()
        async with pool.acquire() as conn:
            if scenario_id and action_type:
                rows = await conn.fetch(
                    "SELECT * FROM action_log WHERE scenario_id = $1 AND action_type = $2 ORDER BY created_at DESC LIMIT $3 OFFSET $4",
                    scenario_id,
                    action_type,
                    limit,
                    offset,
                )
            elif scenario_id:
                rows = await conn.fetch(
                    "SELECT * FROM action_log WHERE scenario_id = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3",
                    scenario_id,
                    limit,
                    offset,
                )
            elif action_type:
                rows = await conn.fetch(
                    "SELECT * FROM action_log WHERE action_type = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3",
                    action_type,
                    limit,
                    offset,
                )
            else:
                rows = await conn.fetch(
                    "SELECT * FROM action_log ORDER BY created_at DESC LIMIT $1 OFFSET $2",
                    limit,
                    offset,
                )
        return [
            {
                "id": row["id"],
                "scenario_id": row["scenario_id"],
                "action_type": row["action_type"],
                "actor": row["actor"],
                "payload": json.loads(row["payload"]) if row["payload"] else None,
                "created_at": row["created_at"],
            }
            for row in rows
        ]
