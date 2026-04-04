from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException

from app.database import get_pool

router = APIRouter()


@router.get("/api/scenario/{scenario_id}/status")
async def get_simulation_status(scenario_id: str):
    pool = get_pool()
    async with pool.acquire() as conn:
        scenario = await conn.fetchrow(
            "SELECT status, seed_status, simulation_status FROM scenarios WHERE id = $1",
            scenario_id,
        )
        if not scenario:
            raise HTTPException(404, "Scenario not found")

        latest_event = await conn.fetchrow(
            """SELECT event_type, payload, created_at
               FROM simulation_events
               WHERE scenario_id = $1
               ORDER BY sequence_num DESC LIMIT 1""",
            scenario_id,
        )

    phase = ""
    current_round = 0
    if latest_event:
        payload = json.loads(latest_event["payload"]) if isinstance(latest_event["payload"], str) else latest_event["payload"]
        phase = payload.get("phase", "")
        current_round = payload.get("round", 0)

    sim_status = scenario["simulation_status"]
    is_wargame = False
    async with pool.acquire() as conn:
        params_row = await conn.fetchrow(
            "SELECT simulation_params FROM scenarios WHERE id = $1", scenario_id,
        )
        if params_row and params_row["simulation_params"]:
            try:
                params = json.loads(params_row["simulation_params"]) if isinstance(params_row["simulation_params"], str) else params_row["simulation_params"]
                is_wargame = params.get("wargame_enabled", False)
            except (json.JSONDecodeError, TypeError):
                pass

    if sim_status == "running":
        phase_map = {
            "": "starting",
            "analyzing": "simulating:ontology",
            "building": "simulating:graph_build",
            "configuring": "simulating:prepare",
            "simulating": "simulating:wargame:simulation" if is_wargame else "simulating:running",
            "reporting": "simulating:report",
        }
        compat_status = phase_map.get(phase, "simulating:running")
    else:
        compat_status = sim_status

    return {
        "status": compat_status,
        "seed_status": scenario["seed_status"],
        "simulation_status": sim_status,
        "phase": phase,
        "current_round": current_round,
    }


@router.get("/api/scenario/{scenario_id}/results")
async def get_simulation_results(scenario_id: str):
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT event_type, payload, sequence_num, created_at
               FROM simulation_events
               WHERE scenario_id = $1
               ORDER BY sequence_num""",
            scenario_id,
        )

    events = []
    for row in rows:
        payload = json.loads(row["payload"]) if isinstance(row["payload"], str) else row["payload"]
        events.append({
            "type": row["event_type"],
            "sequence_num": row["sequence_num"],
            "created_at": str(row["created_at"]),
            **payload,
        })

    round_complete = [e for e in events if e["type"] == "round_complete"]
    agent_actions = [e for e in events if e["type"] == "agent_action"]

    return {
        "scenario_id": scenario_id,
        "total_events": len(events),
        "total_rounds": len(round_complete),
        "total_actions": len(agent_actions),
        "events": events,
    }


@router.get("/api/scenario/{scenario_id}/report")
async def get_simulation_report(scenario_id: str):
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT payload, created_at
               FROM simulation_events
               WHERE scenario_id = $1 AND event_type = 'report_ready'
               ORDER BY sequence_num DESC LIMIT 1""",
            scenario_id,
        )

    if not row:
        briefing = await _get_briefing_fallback(scenario_id)
        if briefing:
            return briefing
        raise HTTPException(404, "Report not found")

    payload = json.loads(row["payload"]) if isinstance(row["payload"], str) else row["payload"]
    return {
        "scenario_id": scenario_id,
        "report_id": payload.get("report_id", ""),
        "created_at": str(row["created_at"]),
        **payload,
    }


async def _get_briefing_fallback(scenario_id: str) -> dict | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT content, version, created_at FROM briefings WHERE scenario_id = $1 ORDER BY version DESC LIMIT 1",
            scenario_id,
        )
    if not row:
        return None
    return {
        "scenario_id": scenario_id,
        "content": row["content"],
        "version": row["version"],
        "created_at": str(row["created_at"]),
    }


@router.get("/api/scenario/{scenario_id}/geojson")
async def get_simulation_geojson(scenario_id: str):
    pool = get_pool()
    async with pool.acquire() as conn:
        edges = await conn.fetch(
            """SELECT edge_type, source_entity_id, target_entity_id, properties
               FROM ontology_edge_history
               WHERE scenario_id = $1
               ORDER BY valid_from""",
            scenario_id,
        )

        actors = await conn.fetch(
            """SELECT payload FROM simulation_events
               WHERE scenario_id = $1 AND event_type = 'agent_action'
               ORDER BY sequence_num""",
            scenario_id,
        )

    features = []
    for edge in edges:
        props = json.loads(edge["properties"]) if isinstance(edge["properties"], str) else (edge["properties"] or {})
        features.append({
            "type": "Feature",
            "geometry": None,
            "properties": {
                "edge_type": edge["edge_type"],
                "source": edge["source_entity_id"],
                "target": edge["target_entity_id"],
                **props,
            },
        })

    return {"type": "FeatureCollection", "features": features}
