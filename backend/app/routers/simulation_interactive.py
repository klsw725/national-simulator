import json
import logging
import uuid
from datetime import datetime, timezone

import asyncpg
import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request

from app.clients.mirofish import MiroFishClient
from app.clients.shadowbroker import ShadowBrokerClient
from app.database import get_db, get_db_tx
from app.models.scenario import SimulationParams
from app.routers._helpers import get_mf_client, get_sb_client, get_sim_row
from app.services.action_logger import ActionLogger
from app.services.simulation_orchestrator import SimulationOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scenario", tags=["simulation-interactive"])


@router.get("/{scenario_id}/interactive_status")
async def get_interactive_status(
    scenario_id: str,
    conn: asyncpg.Connection = Depends(get_db),
):
    scenario = await conn.fetchrow(
        "SELECT id, status, simulation_status FROM scenarios WHERE id = $1", scenario_id
    )
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    result = await conn.fetchrow(
        "SELECT status, checkpoint_data FROM simulation_results WHERE scenario_id = $1 ORDER BY created_at DESC LIMIT 1",
        scenario_id,
    )

    injected_count = await conn.fetchval(
        "SELECT COUNT(*) FROM injected_events WHERE scenario_id = $1 AND status = 'pending'",
        scenario_id,
    )

    tension_count = await conn.fetchval(
        "SELECT COUNT(*) FROM decision_points WHERE scenario_id = $1 AND type = 'tension_alert' AND status = 'pending'",
        scenario_id,
    )

    checkpoint = json.loads(result["checkpoint_data"]) if result and result["checkpoint_data"] else {}
    sim_status = result["status"] if result else "pending"
    is_paused = sim_status.startswith("paused:")

    return {
        "scenario_id": scenario_id,
        "simulation_status": sim_status,
        "current_round": checkpoint.get("current_round", 0),
        "max_rounds": checkpoint.get("max_rounds", 10),
        "is_paused": is_paused,
        "pause_reason": checkpoint.get("pause_reason") if is_paused else None,
        "injected_events_count": injected_count,
        "tension_alerts": tension_count,
    }


@router.post("/{scenario_id}/simulation/pause")
async def pause_simulation(
    scenario_id: str,
    conn: asyncpg.Connection = Depends(get_db_tx),
):
    result = await conn.fetchrow(
        "SELECT id, status, mirofish_simulation_id, checkpoint_data FROM simulation_results WHERE scenario_id = $1 ORDER BY created_at DESC LIMIT 1",
        scenario_id,
    )
    if not result:
        raise HTTPException(status_code=404, detail="No simulation found")

    status = result["status"]
    if not status.startswith("simulating:"):
        raise HTTPException(status_code=409, detail=f"Cannot pause simulation in status: {status}")

    mf_sim_id = result["mirofish_simulation_id"]
    if mf_sim_id:
        from app.clients.mirofish import MiroFishClient
        from app.config import settings
        client = MiroFishClient(settings.mirofish_url)
        try:
            await client.stop_simulation(mf_sim_id)
        finally:
            await client.close()

    checkpoint = json.loads(result["checkpoint_data"]) if result["checkpoint_data"] else {}
    checkpoint["pause_reason"] = "manual"
    now = datetime.now(timezone.utc).isoformat()

    await conn.execute(
        "UPDATE simulation_results SET status = $1, checkpoint_data = $2 WHERE id = $3",
        f"paused:round_{checkpoint.get('current_round', 0)}",
        json.dumps(checkpoint),
        result["id"],
    )
    await conn.execute(
        "UPDATE scenarios SET simulation_status = 'paused', updated_at = $1 WHERE id = $2",
        now, scenario_id,
    )

    return {"status": "paused", "round": checkpoint.get("current_round", 0)}


@router.post("/{scenario_id}/simulation/resume")
async def resume_simulation(
    scenario_id: str,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    mf_client: MiroFishClient = Depends(get_mf_client),
    sb_client: ShadowBrokerClient = Depends(get_sb_client),
    conn: asyncpg.Connection = Depends(get_db_tx),
):
    result = await conn.fetchrow(
        "SELECT id, status, checkpoint_data, mirofish_simulation_id, mirofish_project_id, graph_id FROM simulation_results WHERE scenario_id = $1 ORDER BY created_at DESC LIMIT 1",
        scenario_id,
    )
    if not result:
        raise HTTPException(status_code=404, detail="No simulation found")

    status = result["status"]
    if not status.startswith("paused:"):
        raise HTTPException(status_code=409, detail=f"Simulation not paused, status: {status}")

    checkpoint = json.loads(result["checkpoint_data"]) if result["checkpoint_data"] else {}
    scenario = await conn.fetchrow("SELECT * FROM scenarios WHERE id = $1", scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    sim_params_raw = scenario["simulation_params"]
    sim_params = SimulationParams.model_validate_json(sim_params_raw or "{}")

    now = datetime.now(timezone.utc).isoformat()
    await conn.execute(
        "UPDATE simulation_results SET status = 'simulating:running' WHERE id = $1",
        result["id"],
    )
    await conn.execute(
        "UPDATE scenarios SET simulation_status = 'simulating:running', updated_at = $1 WHERE id = $2",
        now, scenario_id,
    )

    seed = await conn.fetchrow(
        "SELECT text FROM seeds WHERE scenario_id = $1 ORDER BY created_at DESC LIMIT 1",
        scenario_id,
    )
    seed_text = seed["text"] if seed else ""

    current_round = checkpoint.get("current_round", 0)
    remaining_rounds = scenario["max_rounds"] - current_round

    if remaining_rounds <= 0:
        await conn.execute(
            "UPDATE simulation_results SET status = 'completed' WHERE id = $1",
            result["id"],
        )
        return {"status": "completed", "message": "All rounds already completed"}

    recovery_point = "run_simulation"

    orchestrator = SimulationOrchestrator(mf_client, sb_client=sb_client)
    background_tasks.add_task(
        orchestrator.run_from_failure,
        scenario_id,
        result["id"],
        seed_text,
        remaining_rounds,
        recovery_point,
        result["mirofish_project_id"] or "",
        result["graph_id"] or "",
        result["mirofish_simulation_id"] or "",
        sim_params,
    )

    return {
        "status": "resuming",
        "from_round": current_round,
        "remaining_rounds": remaining_rounds,
    }


@router.post("/{scenario_id}/simulation/inject_event", status_code=201)
async def inject_event(
    scenario_id: str,
    request: Request,
    conn: asyncpg.Connection = Depends(get_db),
):
    scenario = await conn.fetchrow("SELECT id FROM scenarios WHERE id = $1", scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    result = await conn.fetchrow(
        "SELECT id, status, checkpoint_data FROM simulation_results WHERE scenario_id = $1 ORDER BY created_at DESC LIMIT 1",
        scenario_id,
    )
    if not result:
        raise HTTPException(status_code=404, detail="No simulation found")

    body = await request.json()

    from app.models.interactive import InjectEventRequest
    event_data = InjectEventRequest(**body)

    checkpoint = json.loads(result["checkpoint_data"]) if result["checkpoint_data"] else {}
    event_id = f"evt_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()

    await conn.execute(
        """INSERT INTO injected_events (id, scenario_id, result_id, event_type, content, target_agents, injected_at_round, status, created_at)
           VALUES ($1, $2, $3, $4, $5, $6, $7, 'pending', $8)""",
        event_id,
        scenario_id,
        result["id"],
        event_data.event_type,
        event_data.content,
        json.dumps(event_data.target_agents),
        checkpoint.get("current_round", 0),
        now,
    )

    return {
        "event_id": event_id,
        "status": "pending",
        "injected_at_round": checkpoint.get("current_round", 0),
    }


@router.post("/{scenario_id}/simulation/whatif", status_code=201)
async def create_whatif_branch(
    scenario_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    mf_client: MiroFishClient = Depends(get_mf_client),
    sb_client: ShadowBrokerClient = Depends(get_sb_client),
    conn: asyncpg.Connection = Depends(get_db),
):
    body = await request.json()

    from app.models.interactive import WhatIfCreateRequest
    from app.services.whatif_engine import WhatIfEngine

    req = WhatIfCreateRequest(**body)

    engine = WhatIfEngine(mf_client, sb_client)

    try:
        result = await engine.create_branch(scenario_id, req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    background_tasks.add_task(
        engine.run_branch_pipeline,
        scenario_id,
        result["branch_id"],
        result["result_id"],
        result["augmented_seed"],
        result["max_rounds"],
        result["simulation_params"],
    )

    return {
        "branch_id": result["branch_id"],
        "status": "running",
        "modification": req.modification,
    }


@router.get("/{scenario_id}/simulation/whatif")
async def list_whatif_branches(
    scenario_id: str,
    conn: asyncpg.Connection = Depends(get_db),
):
    rows = await conn.fetch(
        """SELECT id, scenario_id, parent_result_id, branch_result_id,
                  branch_point_round, modification, execution_mode,
                  world_model_strategy, status, comparison_data,
                  created_at, completed_at
           FROM whatif_branches
           WHERE scenario_id = $1
           ORDER BY created_at DESC""",
        scenario_id,
    )
    branches = []
    for row in rows:
        comp = json.loads(row["comparison_data"]) if row["comparison_data"] else None
        branches.append({
            "id": row["id"],
            "scenario_id": row["scenario_id"],
            "parent_result_id": row["parent_result_id"],
            "branch_result_id": row["branch_result_id"],
            "branch_point_round": row["branch_point_round"],
            "modification": row["modification"],
            "execution_mode": row["execution_mode"],
            "world_model_strategy": row["world_model_strategy"],
            "status": row["status"],
            "comparison_data": comp,
            "created_at": row["created_at"],
            "completed_at": row["completed_at"],
        })
    return branches


@router.get("/{scenario_id}/simulation/whatif/{branch_id}")
async def get_whatif_branch(
    scenario_id: str,
    branch_id: str,
    conn: asyncpg.Connection = Depends(get_db),
):
    row = await conn.fetchrow(
        "SELECT * FROM whatif_branches WHERE id = $1 AND scenario_id = $2",
        branch_id, scenario_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Branch not found")

    comp = json.loads(row["comparison_data"]) if row["comparison_data"] else None
    return {
        "id": row["id"],
        "scenario_id": row["scenario_id"],
        "parent_result_id": row["parent_result_id"],
        "branch_result_id": row["branch_result_id"],
        "branch_point_round": row["branch_point_round"],
        "modification": row["modification"],
        "execution_mode": row["execution_mode"],
        "world_model_strategy": row["world_model_strategy"],
        "status": row["status"],
        "comparison_data": comp,
        "created_at": row["created_at"],
        "completed_at": row["completed_at"],
    }


@router.get("/{scenario_id}/simulation/whatif/{branch_id}/compare")
async def compare_whatif_branch(
    scenario_id: str,
    branch_id: str,
    mf_client: MiroFishClient = Depends(get_mf_client),
    sb_client: ShadowBrokerClient = Depends(get_sb_client),
    conn: asyncpg.Connection = Depends(get_db),
):
    row = await conn.fetchrow(
        "SELECT id, status FROM whatif_branches WHERE id = $1 AND scenario_id = $2",
        branch_id, scenario_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Branch not found")
    if row["status"] != "completed":
        raise HTTPException(status_code=409, detail=f"Branch not completed, status: {row['status']}")

    from app.services.whatif_engine import WhatIfEngine

    engine = WhatIfEngine(mf_client, sb_client)

    try:
        comparison = await engine.compare(branch_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return comparison.model_dump()


@router.get("/{scenario_id}/env_status")
async def get_env_status(
    scenario_id: str,
    mf_client: MiroFishClient = Depends(get_mf_client),
    conn: asyncpg.Connection = Depends(get_db),
):
    row = await get_sim_row(conn, scenario_id)
    mf_sim_id = row["mirofish_simulation_id"]
    if not mf_sim_id:
        return {"env_alive": False, "message": "MiroFish simulation not yet created"}

    try:
        return await mf_client.get_env_status(mf_sim_id)
    except (httpx.HTTPError, RuntimeError, TimeoutError) as e:
        logger.warning("Failed to fetch env status for scenario %s: %s", scenario_id, e)
        return {"env_alive": False, "message": "MiroFish unavailable"}


@router.post("/{scenario_id}/interview")
async def interview_agent(
    scenario_id: str,
    request: Request,
    mf_client: MiroFishClient = Depends(get_mf_client),
    conn: asyncpg.Connection = Depends(get_db),
):
    row = await get_sim_row(conn, scenario_id)
    mf_sim_id = row["mirofish_simulation_id"]
    if not mf_sim_id:
        raise HTTPException(status_code=400, detail="Simulation not started")

    body = await request.json()
    try:
        return await mf_client.interview_agent(
            simulation_id=mf_sim_id,
            agent_id=body["agent_id"],
            prompt=body["prompt"],
            platform=body.get("platform"),
            timeout=body.get("timeout", 60),
        )
    except KeyError as e:
        raise HTTPException(status_code=400, detail=f"Missing field: {e}") from e
    except (httpx.HTTPError, RuntimeError, TimeoutError) as e:
        logger.exception("Interview failed for scenario %s", scenario_id)
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.post("/{scenario_id}/interview/all")
async def interview_all_agents(
    scenario_id: str,
    request: Request,
    mf_client: MiroFishClient = Depends(get_mf_client),
    conn: asyncpg.Connection = Depends(get_db),
):
    row = await get_sim_row(conn, scenario_id)
    mf_sim_id = row["mirofish_simulation_id"]
    if not mf_sim_id:
        raise HTTPException(status_code=400, detail="Simulation not started")

    body = await request.json()
    try:
        return await mf_client.interview_all_agents(
            simulation_id=mf_sim_id,
            prompt=body["prompt"],
            platform=body.get("platform"),
            timeout=body.get("timeout", 180),
        )
    except KeyError as e:
        raise HTTPException(status_code=400, detail=f"Missing field: {e}") from e
    except (httpx.HTTPError, RuntimeError, TimeoutError) as e:
        logger.exception("Interview all failed for scenario %s", scenario_id)
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.post("/{scenario_id}/interview/batch")
async def interview_agents_batch(
    scenario_id: str,
    request: Request,
    mf_client: MiroFishClient = Depends(get_mf_client),
    conn: asyncpg.Connection = Depends(get_db),
):
    row = await get_sim_row(conn, scenario_id)
    mf_sim_id = row["mirofish_simulation_id"]
    if not mf_sim_id:
        raise HTTPException(status_code=400, detail="Simulation not started")

    body = await request.json()
    try:
        return await mf_client.interview_agents_batch(
            simulation_id=mf_sim_id,
            interviews=body["interviews"],
            platform=body.get("platform"),
            timeout=body.get("timeout", 120),
        )
    except KeyError as e:
        raise HTTPException(status_code=400, detail=f"Missing field: {e}") from e
    except (httpx.HTTPError, RuntimeError, TimeoutError) as e:
        logger.exception("Batch interview failed for scenario %s", scenario_id)
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.get("/{scenario_id}/interview/history")
async def get_interview_history(
    scenario_id: str,
    agent_id: int | None = None,
    limit: int = 50,
    mf_client: MiroFishClient = Depends(get_mf_client),
    conn: asyncpg.Connection = Depends(get_db),
):
    row = await get_sim_row(conn, scenario_id)
    mf_sim_id = row["mirofish_simulation_id"]
    if not mf_sim_id:
        return {"interviews": [], "total": 0}

    try:
        return await mf_client.get_interview_history(mf_sim_id, agent_id=agent_id, limit=limit)
    except (httpx.HTTPError, RuntimeError, TimeoutError) as e:
        logger.exception("Interview history failed for scenario %s", scenario_id)
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.post("/{scenario_id}/close_env")
async def close_simulation_env(
    scenario_id: str,
    request: Request,
    mf_client: MiroFishClient = Depends(get_mf_client),
    conn: asyncpg.Connection = Depends(get_db),
):
    row = await get_sim_row(conn, scenario_id)
    mf_sim_id = row["mirofish_simulation_id"]
    if not mf_sim_id:
        raise HTTPException(status_code=400, detail="Simulation not started")

    body = await request.json()
    try:
        return await mf_client.close_env(mf_sim_id, timeout=body.get("timeout", 30))
    except (httpx.HTTPError, RuntimeError, TimeoutError) as e:
        logger.exception("Close env failed for scenario %s", scenario_id)
        raise HTTPException(status_code=502, detail=str(e)) from e
