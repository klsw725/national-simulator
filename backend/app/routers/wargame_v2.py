from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.database import get_pool

router = APIRouter()

CHECKPOINT_TABLE = "checkpoints"


async def _get_latest_state(scenario_id: str) -> dict | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""SELECT checkpoint
                FROM {CHECKPOINT_TABLE}
                WHERE thread_id = $1
                ORDER BY checkpoint_id DESC LIMIT 1""",
            scenario_id,
        )
    if not row:
        return None
    checkpoint = row["checkpoint"]
    if isinstance(checkpoint, str):
        checkpoint = json.loads(checkpoint)
    channel_values = checkpoint.get("channel_values", {})
    return channel_values


async def _get_pending_decision(scenario_id: str) -> dict | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT payload FROM simulation_events
               WHERE scenario_id = $1 AND event_type = 'intervention_required'
               ORDER BY sequence_num DESC LIMIT 1""",
            scenario_id,
        )
    if not row:
        return None
    payload = json.loads(row["payload"]) if isinstance(row["payload"], str) else row["payload"]
    return payload.get("decision_point")


@router.get("/api/scenario/{scenario_id}/wargame_status")
async def get_wargame_status(scenario_id: str):
    pool = get_pool()
    async with pool.acquire() as conn:
        scenario_row = await conn.fetchrow(
            "SELECT simulation_status FROM scenarios WHERE id = $1", scenario_id,
        )
    if not scenario_row:
        raise HTTPException(404, "Scenario not found")

    if scenario_row["simulation_status"] == "completed":
        state = await _get_latest_state(scenario_id) or {}
        tension = state.get("tension_levels", {})
        actor_states = state.get("actor_states", {})
        return {
            "phase": "completed",
            "round": state.get("current_round", 0),
            "totalRounds": state.get("max_rounds", 10),
            "role": "actor_role",
            "actorId": None,
            "tension": max(tension.values()) if tension else 0.0,
            "actorStates": {
                k: {
                    "actor_id": k,
                    "name": v.get("name", k),
                    "threat_perception": v.get("threat_perception", 0),
                    "domestic_pressure": v.get("domestic_pressure", 0),
                    "resource_level": v.get("resource_level", 1),
                }
                for k, v in actor_states.items()
            },
            "briefing": None,
            "decisionPoint": None,
        }

    state = await _get_latest_state(scenario_id)
    if not state:
        raise HTTPException(404, "No simulation state found")

    actors_raw = state.get("actors", {})
    actor_states = state.get("actor_states", {})
    tension = state.get("tension_levels", {})
    decision_point = state.get("decision_point")
    if not decision_point:
        decision_point = await _get_pending_decision(scenario_id)

    phase_map = {
        "analyzing": "simulation",
        "building": "simulation",
        "configuring": "simulation",
        "simulating": "simulation",
        "reporting": "simulation",
    }
    raw_phase = state.get("phase", "simulation")
    mapped_phase = phase_map.get(raw_phase, raw_phase)

    briefing = None
    if state.get("situation_summary"):
        briefing = {
            "round": state.get("current_round", 0),
            "key_events": [],
            "state_deltas": {},
            "analysis_text": state["situation_summary"][:2000],
        }

    return {
        "phase": mapped_phase if not decision_point else "decision",
        "round": state.get("current_round", 0),
        "totalRounds": state.get("max_rounds", 10),
        "role": "actor_role",
        "actorId": None,
        "tension": max(tension.values()) if tension else 0.0,
        "actorStates": {
            k: {
                "actor_id": k,
                "name": v.get("name", k),
                "threat_perception": v.get("threat_perception", 0),
                "domestic_pressure": v.get("domestic_pressure", 0),
                "resource_level": v.get("resource_level", 1),
            }
            for k, v in actor_states.items()
        },
        "briefing": briefing,
        "decisionPoint": decision_point,
    }


class ContinueRequest(BaseModel):
    edits: dict | None = None


@router.post("/api/scenario/{scenario_id}/continue", status_code=202)
async def continue_simulation(scenario_id: str, body: ContinueRequest | None = None):
    pool = get_pool()
    command = json.dumps({
        "type": "resume_simulation",
        "scenario_id": scenario_id,
    }, ensure_ascii=False)
    async with pool.acquire() as conn:
        await conn.execute("SELECT pg_notify($1, $2)", "sim_commands", command)
    return {"status": "resumed"}


@router.get("/api/scenario/{scenario_id}/checkpoint")
async def get_checkpoint(scenario_id: str):
    state = await _get_latest_state(scenario_id)
    if not state:
        raise HTTPException(404, "No checkpoint found")

    decision_point = state.get("decision_point")
    if not decision_point:
        decision_point = await _get_pending_decision(scenario_id)
    status = state.get("status", "")
    if decision_point and status == "running":
        status = "paused"

    return {
        "scenario_id": scenario_id,
        "current_round": state.get("current_round", 0),
        "max_rounds": state.get("max_rounds", 10),
        "phase": state.get("phase", ""),
        "status": status,
        "decision_point": decision_point,
        "has_pending_decision": decision_point is not None,
    }


@router.post("/api/scenario/{scenario_id}/retry", status_code=202)
async def retry_simulation(scenario_id: str):
    pool = get_pool()
    async with pool.acquire() as conn:
        scenario = await conn.fetchrow(
            "SELECT question, region_bbox FROM scenarios WHERE id = $1", scenario_id,
        )
    if not scenario:
        raise HTTPException(404, "Scenario not found")

    region_bbox = json.loads(scenario["region_bbox"]) if scenario["region_bbox"] else []
    command = json.dumps({
        "type": "start_simulation",
        "scenario_id": scenario_id,
        "seed_text": scenario["question"],
        "region_bbox": region_bbox,
        "retry": True,
    }, ensure_ascii=False)
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SELECT pg_notify($1, $2)", "sim_commands", command)
    return {"status": "retrying"}
