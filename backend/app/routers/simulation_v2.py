from __future__ import annotations

import json

from fastapi import APIRouter
from pydantic import BaseModel

from app.database import get_pool

router = APIRouter()


class StartSimulationRequest(BaseModel):
    seed_text: str = ""
    max_rounds: int = 10


class DecisionRequest(BaseModel):
    decision_point_id: str
    chosen_action: dict


@router.post("/api/scenario/{scenario_id}/start_v2")
async def start_simulation_v2(scenario_id: str, body: StartSimulationRequest):
    pool = get_pool()
    payload = json.dumps({
        "type": "start_simulation",
        "scenario_id": scenario_id,
        "seed_text": body.seed_text,
        "max_rounds": body.max_rounds,
    }, ensure_ascii=False)
    async with pool.acquire() as conn:
        await conn.execute("SELECT pg_notify($1, $2)", "sim_commands", payload)
    return {"status": "started", "scenario_id": scenario_id}


@router.post("/api/scenario/{scenario_id}/decide_v2")
async def submit_decision_v2(scenario_id: str, body: DecisionRequest):
    pool = get_pool()
    payload = json.dumps({
        "type": "user_decision",
        "scenario_id": scenario_id,
        "decision_point_id": body.decision_point_id,
        "chosen_action": body.chosen_action,
    }, ensure_ascii=False)
    async with pool.acquire() as conn:
        await conn.execute("SELECT pg_notify($1, $2)", "sim_commands", payload)
    return {"status": "decision_submitted"}
