from __future__ import annotations

import json

from fastapi import APIRouter
from fastapi import HTTPException
from pydantic import BaseModel

from app.database import get_pool

router = APIRouter()


async def _load_seed_context(conn, scenario_id: str):
    scenario = await conn.fetchrow(
        "SELECT question, region_bbox, region_name, seed_status FROM scenarios WHERE id = $1",
        scenario_id,
    )
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    seed = await conn.fetchrow(
        "SELECT text FROM seeds WHERE scenario_id = $1 ORDER BY created_at DESC LIMIT 1",
        scenario_id,
    )
    if scenario["seed_status"] != "completed" or not seed or not seed["text"]:
        raise HTTPException(
            status_code=400,
            detail="Seed must be generated before starting simulation",
        )

    return scenario, seed


class StartSimulationRequest(BaseModel):
    seed_text: str = ""
    max_rounds: int = 10


class DecisionRequest(BaseModel):
    decision_point_id: str
    chosen_action: dict


class LegacySimulateRequest(BaseModel):
    mode: str = "auto"


@router.post("/api/scenario/{scenario_id}/simulate", status_code=202)
async def start_simulation_legacy(scenario_id: str, body: LegacySimulateRequest | None = None):
    pool = get_pool()
    async with pool.acquire() as conn:
        scenario, seed = await _load_seed_context(conn, scenario_id)
        await conn.execute(
            "UPDATE scenarios SET status = 'running', simulation_status = 'running' WHERE id = $1",
            scenario_id,
        )
    question = scenario["question"]
    region_name = scenario["region_name"]
    seed_text = seed["text"]
    region_bbox = json.loads(scenario["region_bbox"]) if scenario and scenario["region_bbox"] else []
    payload = json.dumps({
        "type": "start_simulation",
        "scenario_id": scenario_id,
        "seed_text": seed_text,
        "max_rounds": 10,
        "region_bbox": region_bbox,
        "region_name": region_name,
        "question": question,
    }, ensure_ascii=False)
    async with pool.acquire() as conn:
        await conn.execute("SELECT pg_notify($1, $2)", "sim_commands", payload)
    return {"status": "started", "pipeline_mode": body.mode if body else "auto"}


@router.post("/api/scenario/{scenario_id}/start_v2")
async def start_simulation_v2(scenario_id: str, body: StartSimulationRequest):
    pool = get_pool()
    async with pool.acquire() as conn:
        scenario, seed = await _load_seed_context(conn, scenario_id)
        await conn.execute(
            "UPDATE scenarios SET status = 'running', simulation_status = 'running' WHERE id = $1",
            scenario_id,
        )
    region_bbox = json.loads(scenario["region_bbox"]) if scenario and scenario["region_bbox"] else []
    question = scenario["question"]
    region_name = scenario["region_name"]
    seed_text = body.seed_text or seed["text"]
    payload = json.dumps({
        "type": "start_simulation",
        "scenario_id": scenario_id,
        "seed_text": seed_text,
        "max_rounds": body.max_rounds,
        "region_bbox": region_bbox,
        "region_name": region_name,
        "question": question,
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
