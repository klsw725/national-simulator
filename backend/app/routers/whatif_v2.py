from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.database import get_pool

router = APIRouter()


class WhatIfCreateRequest(BaseModel):
    parent_result_id: str = ""
    branch_point_round: int = 0
    modification: str = ""
    chosen_action: dict | None = None


@router.post("/api/scenario/{scenario_id}/simulation/whatif")
async def create_whatif_branch(scenario_id: str, body: WhatIfCreateRequest):
    pool = get_pool()
    branch_id = f"wif_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()

    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO whatif_branches
               (id, scenario_id, parent_result_id, branch_point_round,
                modification, status, created_at)
               VALUES ($1, $2, $3, $4, $5, 'running', $6)""",
            branch_id, scenario_id, body.parent_result_id,
            body.branch_point_round, body.modification, now,
        )

    command = json.dumps({
        "type": "start_whatif",
        "scenario_id": scenario_id,
        "branch_id": branch_id,
        "branch_point_round": body.branch_point_round,
        "modification": body.modification,
        "chosen_action": body.chosen_action,
    }, ensure_ascii=False)
    async with pool.acquire() as conn:
        await conn.execute("SELECT pg_notify($1, $2)", "sim_commands", command)

    return {
        "branch_id": branch_id,
        "status": "running",
        "modification": body.modification,
    }


@router.get("/api/scenario/{scenario_id}/simulation/whatif")
async def list_whatif_branches(scenario_id: str):
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, parent_result_id, branch_point_round, modification,
                      status, comparison_data, created_at, completed_at
               FROM whatif_branches
               WHERE scenario_id = $1
               ORDER BY created_at DESC""",
            scenario_id,
        )

    return [
        {
            "id": row["id"],
            "parent_result_id": row["parent_result_id"],
            "branch_point_round": row["branch_point_round"],
            "modification": row["modification"],
            "status": row["status"],
            "comparison_data": json.loads(row["comparison_data"]) if row["comparison_data"] else None,
            "created_at": str(row["created_at"]),
            "completed_at": str(row["completed_at"]) if row["completed_at"] else None,
        }
        for row in rows
    ]


@router.get("/api/scenario/{scenario_id}/simulation/whatif/{branch_id}")
async def get_whatif_branch(scenario_id: str, branch_id: str):
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT id, parent_result_id, branch_point_round, modification,
                      status, comparison_data, created_at, completed_at
               FROM whatif_branches
               WHERE id = $1 AND scenario_id = $2""",
            branch_id, scenario_id,
        )

    if not row:
        raise HTTPException(404, "Branch not found")

    branch_events = []
    async with pool.acquire() as conn:
        events = await conn.fetch(
            """SELECT event_type, payload, sequence_num, created_at
               FROM simulation_events
               WHERE scenario_id = $1
               ORDER BY sequence_num""",
            branch_id,
        )
    for evt in events:
        payload = json.loads(evt["payload"]) if isinstance(evt["payload"], str) else evt["payload"]
        branch_events.append({
            "type": evt["event_type"],
            "sequence_num": evt["sequence_num"],
            **payload,
        })

    return {
        "id": row["id"],
        "scenario_id": scenario_id,
        "branch_point_round": row["branch_point_round"],
        "modification": row["modification"],
        "status": row["status"],
        "events": branch_events,
        "created_at": str(row["created_at"]),
    }


@router.get("/api/scenario/{scenario_id}/simulation/whatif/{branch_id}/compare")
async def compare_whatif(scenario_id: str, branch_id: str):
    pool = get_pool()

    async def _get_actions(sid: str) -> list[dict]:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT payload FROM simulation_events
                   WHERE scenario_id = $1 AND event_type = 'agent_action'
                   ORDER BY sequence_num""",
                sid,
            )
        return [
            json.loads(r["payload"]) if isinstance(r["payload"], str) else r["payload"]
            for r in rows
        ]

    original_actions = await _get_actions(scenario_id)
    branch_actions = await _get_actions(branch_id)

    original_actors: dict[str, int] = {}
    for a in original_actions:
        actor = a.get("actor", "?")
        original_actors[actor] = original_actors.get(actor, 0) + 1

    branch_actors: dict[str, int] = {}
    for a in branch_actions:
        actor = a.get("actor", "?")
        branch_actors[actor] = branch_actors.get(actor, 0) + 1

    return {
        "scenario_id": scenario_id,
        "branch_id": branch_id,
        "original": {
            "total_actions": len(original_actions),
            "actions_by_actor": original_actors,
            "actions": original_actions[-20:],
        },
        "branch": {
            "total_actions": len(branch_actions),
            "actions_by_actor": branch_actors,
            "actions": branch_actions[-20:],
        },
    }
