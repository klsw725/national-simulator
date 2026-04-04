from __future__ import annotations

import json

from fastapi import APIRouter

from app.database import get_pool

router = APIRouter()


@router.get("/api/scenario/{scenario_id}/live/actions")
async def get_live_actions(scenario_id: str, offset: int = 0, limit: int = 100):
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT payload, sequence_num, created_at
               FROM simulation_events
               WHERE scenario_id = $1 AND event_type = 'agent_action'
               ORDER BY sequence_num
               OFFSET $2 LIMIT $3""",
            scenario_id, offset, limit,
        )
        count_row = await conn.fetchrow(
            "SELECT count(*) AS cnt FROM simulation_events WHERE scenario_id = $1 AND event_type = 'agent_action'",
            scenario_id,
        )

    actions = []
    for row in rows:
        payload = json.loads(row["payload"]) if isinstance(row["payload"], str) else row["payload"]
        actions.append({
            "sequence_num": row["sequence_num"],
            "created_at": str(row["created_at"]),
            **payload,
        })

    return {"actions": actions, "count": count_row["cnt"] if count_row else 0}


@router.get("/api/scenario/{scenario_id}/live/stats")
async def get_live_stats(scenario_id: str):
    pool = get_pool()
    async with pool.acquire() as conn:
        total = await conn.fetchrow(
            "SELECT count(*) AS cnt FROM simulation_events WHERE scenario_id = $1",
            scenario_id,
        )
        rounds = await conn.fetchrow(
            "SELECT count(*) AS cnt FROM simulation_events WHERE scenario_id = $1 AND event_type = 'round_complete'",
            scenario_id,
        )
        actions = await conn.fetchrow(
            "SELECT count(*) AS cnt FROM simulation_events WHERE scenario_id = $1 AND event_type = 'agent_action'",
            scenario_id,
        )

    return {
        "scenario_id": scenario_id,
        "total_events": total["cnt"] if total else 0,
        "total_rounds": rounds["cnt"] if rounds else 0,
        "total_actions": actions["cnt"] if actions else 0,
    }


@router.get("/api/scenario/{scenario_id}/geopolitics/events")
async def get_geopolitics_events(scenario_id: str, limit: int = 100):
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, action_type, actor_id, target_actor_ids, content, magnitude, round_number, event_at
               FROM geopolitics_events
               WHERE scenario_id = $1
               ORDER BY event_at DESC LIMIT $2""",
            scenario_id, limit,
        )

    return [
        {
            "id": row["id"],
            "action_type": row["action_type"],
            "actor_id": row["actor_id"],
            "target_actor_ids": row["target_actor_ids"],
            "content": row["content"],
            "magnitude": row["magnitude"],
            "round_number": row["round_number"],
            "event_at": str(row["event_at"]),
        }
        for row in rows
    ]


@router.get("/api/scenario/{scenario_id}/geopolitics/timeline")
async def get_geopolitics_timeline(scenario_id: str):
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT event_type, payload, sequence_num, created_at
               FROM simulation_events
               WHERE scenario_id = $1 AND event_type IN ('round_complete', 'phase_change', 'intervention_required')
               ORDER BY sequence_num""",
            scenario_id,
        )

    timeline = []
    for row in rows:
        payload = json.loads(row["payload"]) if isinstance(row["payload"], str) else row["payload"]
        timeline.append({
            "type": row["event_type"],
            "sequence_num": row["sequence_num"],
            "created_at": str(row["created_at"]),
            **payload,
        })

    return {"scenario_id": scenario_id, "timeline": timeline}
