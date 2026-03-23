import json
import logging
import uuid
from datetime import datetime, timezone

import asyncpg
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse, Response

from app.database import get_db, get_pool
from app.models.decision_point import (
    DecisionOption,
    DecisionPointCreate,
    DecisionPointResolveRequest,
    DecisionPointResponse,
)
from app.services.param_recommender import recommend_params
from app.models.result import (
    CheckpointResponse,
    ContinueRequest,
    SimulateRequest,
    SimulationResultResponse,
)
from app.models.scenario import SimulationParams
from app.models.seed import SeedMetadata, SeedResponse
from app.services.action_logger import ActionLogger
from app.services.seed_generator import SeedGenerator
from app.services.simulation_orchestrator import SimulationOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scenario", tags=["simulation"])


def _not_impl(prd: str) -> JSONResponse:
    return JSONResponse(
        status_code=501,
        content={"detail": f"Not implemented. See {prd}."},
    )


@router.post("/{scenario_id}/seed", response_model=SeedResponse, status_code=201)
async def generate_seed(
    scenario_id: str,
    request: Request,
    conn: asyncpg.Connection = Depends(get_db),
):
    """시드 문서를 생성하고 저장한다."""
    scenario = await conn.fetchrow("SELECT * FROM scenarios WHERE id = $1", scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    existing = await conn.fetchrow("SELECT * FROM seeds WHERE scenario_id = $1", scenario_id)
    if existing:
        return _row_to_seed_response(existing)

    sb_client = request.app.state.sb_client
    generator = SeedGenerator(sb_client)

    bbox = json.loads(scenario["region_bbox"])
    question = scenario["question"]
    region_name = scenario["region_name"]

    raw_params = scenario["simulation_params"] if "simulation_params" in scenario else "{}"
    sim_params = SimulationParams.model_validate_json(raw_params or "{}")

    try:
        await conn.execute(
            "UPDATE scenarios SET seed_status = 'generating', updated_at = $1 WHERE id = $2",
            datetime.now(timezone.utc).isoformat(),
            scenario_id,
        )

        result = await generator.generate(
            bbox=bbox,
            question=question,
            region_name=region_name,
            web_search_enabled=sim_params.web_search_enabled,
        )
    except Exception:
        logger.exception("Seed generation failed for scenario %s", scenario_id)
        await conn.execute(
            "UPDATE scenarios SET seed_status = 'failed', updated_at = $1 WHERE id = $2",
            datetime.now(timezone.utc).isoformat(),
            scenario_id,
        )
        raise HTTPException(status_code=500, detail="Seed generation failed")

    seed_id = f"seed_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()

    await conn.execute(
        "INSERT INTO seeds (id, scenario_id, text, metadata, created_at) VALUES ($1, $2, $3, $4, $5)",
        seed_id,
        scenario_id,
        result["text"],
        json.dumps(result["metadata"], ensure_ascii=False),
        now,
    )
    await conn.execute(
        "UPDATE scenarios SET seed_status = 'completed', updated_at = $1 WHERE id = $2",
        now,
        scenario_id,
    )

    used_obs_ids = result["metadata"].get("used_observation_ids", [])
    if used_obs_ids:
        values = [
            (f"so_{uuid.uuid4().hex[:12]}", scenario_id, obs_id, False, now)
            for obs_id in used_obs_ids
        ]
        await conn.executemany(
            "INSERT INTO scenario_observations (id, scenario_id, observation_id, used_in_seed, created_at) VALUES ($1, $2, $3, $4, $5)",
            values,
        )

    await ActionLogger.log(
        "seed.generate",
        scenario_id,
        payload={
            "seed_id": seed_id,
            "vessels_count": result["metadata"].get("vessels_count", 0),
            "resolved_entity_count": result["metadata"].get("resolved_entity_count", 0),
        },
    )

    return SeedResponse(
        id=seed_id,
        scenario_id=scenario_id,
        text=result["text"],
        metadata=SeedMetadata(**result["metadata"]),
        created_at=now,
    )


@router.post("/{scenario_id}/seed_options", status_code=201)
async def generate_seed_options(
    scenario_id: str,
    request: Request,
    num_options: int = 3,
    conn: asyncpg.Connection = Depends(get_db),
):
    scenario = await conn.fetchrow("SELECT * FROM scenarios WHERE id = $1", scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    if num_options < 2 or num_options > 5:
        raise HTTPException(status_code=400, detail="num_options must be between 2 and 5")

    sb_client = request.app.state.sb_client
    generator = SeedGenerator(sb_client)

    bbox = json.loads(scenario["region_bbox"])
    question = scenario["question"]
    region_name = scenario["region_name"]

    raw_params = scenario["simulation_params"] if "simulation_params" in scenario else "{}"
    sim_params = SimulationParams.model_validate_json(raw_params or "{}")

    try:
        result = await generator.generate_options(
            bbox=bbox,
            question=question,
            region_name=region_name,
            num_options=num_options,
            web_search_enabled=sim_params.web_search_enabled,
        )
    except Exception:
        logger.exception("Seed options generation failed for scenario %s", scenario_id)
        raise HTTPException(status_code=500, detail="Seed options generation failed")

    dp_id = f"dp_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()

    await conn.execute(
        """INSERT INTO decision_points
           (id, scenario_id, type, options, recommended, allow_custom, status, created_at)
           VALUES ($1, $2, 'seed_selection', $3, $4, TRUE, 'pending', $5)""",
        dp_id,
        scenario_id,
        json.dumps(result["options"], ensure_ascii=False),
        result["recommended"],
        now,
    )
    await ActionLogger.log(
        "seed_options.generate",
        scenario_id,
        payload={
            "dp_id": dp_id,
            "options_count": len(result["options"]),
            "recommended": result["recommended"],
        },
    )

    dp_row = await conn.fetchrow("SELECT * FROM decision_points WHERE id = $1", dp_id)
    if not dp_row:
        raise HTTPException(status_code=500, detail="Failed to read back created decision point")

    return {
        "scenario_id": scenario_id,
        "decision_point_id": dp_id,
        "options_count": len(result["options"]),
        "recommended": result["recommended"],
        "decision_point": _row_to_decision_point(dp_row),
        "metadata": result["metadata"],
    }


@router.post("/{scenario_id}/recommend_params", status_code=201)
async def recommend_simulation_params(
    scenario_id: str,
    request: Request,
    conn: asyncpg.Connection = Depends(get_db),
):
    scenario = await conn.fetchrow("SELECT * FROM scenarios WHERE id = $1", scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    sb_client = request.app.state.sb_client
    generator = SeedGenerator(sb_client)

    bbox = json.loads(scenario["region_bbox"])
    question = scenario["question"]
    region_name = scenario["region_name"]

    raw_params = scenario["simulation_params"] if "simulation_params" in scenario else "{}"
    sim_params = SimulationParams.model_validate_json(raw_params or "{}")

    try:
        ctx = await generator._collect_and_summarize(
            bbox=bbox,
            question=question,
            region_name=region_name,
            web_search_enabled=sim_params.web_search_enabled,
        )
    except Exception:
        logger.exception("OSINT data collection failed for scenario %s", scenario_id)
        raise HTTPException(status_code=500, detail="OSINT data collection failed")

    result = recommend_params(ctx["metadata"])

    dp_id = f"dp_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()

    await conn.execute(
        """INSERT INTO decision_points
           (id, scenario_id, type, options, recommended, allow_custom, status, created_at)
           VALUES ($1, $2, 'parameter_recommendation', $3, $4, TRUE, 'pending', $5)""",
        dp_id,
        scenario_id,
        json.dumps(result["options"], ensure_ascii=False),
        result["recommended"],
        now,
    )
    await ActionLogger.log(
        "param_recommendation.generate",
        scenario_id,
        payload={
            "dp_id": dp_id,
            "recommended": result["recommended"],
        },
    )

    dp_row = await conn.fetchrow("SELECT * FROM decision_points WHERE id = $1", dp_id)
    if not dp_row:
        raise HTTPException(status_code=500, detail="Failed to read back created decision point")

    return {
        "scenario_id": scenario_id,
        "decision_point_id": dp_id,
        "recommended": result["recommended"],
        "decision_point": _row_to_decision_point(dp_row),
        "metadata": ctx["metadata"],
    }


@router.get("/{scenario_id}/seed", response_model=SeedResponse)
async def get_seed(
    scenario_id: str,
    conn: asyncpg.Connection = Depends(get_db),
):
    row = await conn.fetchrow("SELECT * FROM seeds WHERE scenario_id = $1", scenario_id)
    if not row:
        raise HTTPException(status_code=404, detail="Seed not found for this scenario")
    return _row_to_seed_response(row)


def _row_to_seed_response(row: asyncpg.Record) -> SeedResponse:
    return SeedResponse(
        id=row["id"],
        scenario_id=row["scenario_id"],
        text=row["text"],
        metadata=SeedMetadata(**json.loads(row["metadata"])),
        created_at=row["created_at"],
    )


CHECKPOINT_STEPS = {
    "checkpoint:seed": {"step": "seed", "editable": True},
    "checkpoint:ontology": {"step": "ontology", "editable": False},
    "checkpoint:graph": {"step": "graph", "editable": False},
    "checkpoint:profiles": {"step": "profiles", "editable": False},
    "checkpoint:config": {"step": "config", "editable": True},
    "checkpoint:geopolitics": {"step": "geopolitics", "editable": False},
    "checkpoint:decision": {"step": "decision", "editable": True},
}


async def _generate_decision_options(
    scenario_id: str,
    result_id: str,
    sb_client,
    bbox: list[float],
    question: str,
    region_name: str,
    web_search_enabled: bool,
) -> None:
    pool = get_pool()
    try:
        generator = SeedGenerator(sb_client)
        seed_result = await generator.generate_options(
            bbox=bbox,
            question=question,
            region_name=region_name,
            web_search_enabled=web_search_enabled,
        )

        param_result = recommend_params(seed_result["metadata"])

        now = datetime.now(timezone.utc).isoformat()
        async with pool.acquire() as conn:
            seed_dp_id = f"dp_{uuid.uuid4().hex[:12]}"
            await conn.execute(
                """INSERT INTO decision_points
                   (id, scenario_id, type, options, recommended, allow_custom, status, created_at)
                   VALUES ($1, $2, 'seed_selection', $3, $4, TRUE, 'pending', $5)""",
                seed_dp_id, scenario_id,
                json.dumps(seed_result["options"], ensure_ascii=False),
                seed_result["recommended"], now,
            )

            param_dp_id = f"dp_{uuid.uuid4().hex[:12]}"
            await conn.execute(
                """INSERT INTO decision_points
                   (id, scenario_id, type, options, recommended, allow_custom, status, created_at)
                   VALUES ($1, $2, 'parameter_recommendation', $3, $4, TRUE, 'pending', $5)""",
                param_dp_id, scenario_id,
                json.dumps(param_result["options"], ensure_ascii=False),
                param_result["recommended"], now,
            )

            await conn.execute(
                "UPDATE simulation_results SET status = 'checkpoint:decision' WHERE id = $1",
                result_id,
            )
            await conn.execute(
                "UPDATE scenarios SET simulation_status = 'checkpoint', status = 'checkpoint', updated_at = $1 WHERE id = $2",
                now, scenario_id,
            )

        await ActionLogger.log(
            "decision_options.generated",
            scenario_id,
            payload={"seed_dp_id": seed_dp_id, "param_dp_id": param_dp_id},
        )
        logger.info("[%s] Decision options generated: seed=%s, params=%s", scenario_id, seed_dp_id, param_dp_id)

    except Exception as exc:
        logger.exception("[%s] Decision options generation failed", scenario_id)
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE simulation_results SET status = 'failed' WHERE id = $1",
                result_id,
            )
            now = datetime.now(timezone.utc).isoformat()
            await conn.execute(
                "UPDATE scenarios SET simulation_status = 'failed', status = 'failed', updated_at = $1 WHERE id = $2",
                now, scenario_id,
            )
        try:
            await ActionLogger.log(
                "decision_options.failed", scenario_id,
                payload={"error": str(exc)[:500]},
            )
        except Exception:
            pass


@router.post("/{scenario_id}/simulate", status_code=202)
async def start_simulation(
    scenario_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    body: SimulateRequest | None = None,
    conn: asyncpg.Connection = Depends(get_db),
):
    """시뮬레이션 파이프라인을 시작한다.

    mode="auto": 기존 동작 (전부 자동, 백그라운드 실행)
    mode="checkpoint": 첫 체크포인트(시드 검토)에서 일시정지
    """
    mode = (body.mode if body else "auto") or "auto"
    if mode not in ("auto", "checkpoint", "interactive"):
        raise HTTPException(status_code=400, detail="mode must be 'auto', 'checkpoint', or 'interactive'")

    scenario = await conn.fetchrow("SELECT * FROM scenarios WHERE id = $1", scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    if scenario["seed_status"] != "completed":
        raise HTTPException(
            status_code=400,
            detail="Seed must be generated first (POST /api/scenario/{id}/seed)",
        )

    running = await conn.fetchrow(
        "SELECT * FROM simulation_results WHERE scenario_id = $1 AND status NOT IN ('completed', 'failed')",
        scenario_id,
    )
    if running:
        raise HTTPException(status_code=409, detail="Simulation already in progress")

    seed_row = await conn.fetchrow("SELECT text FROM seeds WHERE scenario_id = $1", scenario_id)
    if not seed_row:
        raise HTTPException(status_code=400, detail="Seed document not found")

    result_id = f"simr_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()

    raw_params_cp = scenario["simulation_params"] if "simulation_params" in scenario else "{}"
    sim_params_cp = SimulationParams.model_validate_json(raw_params_cp or "{}")

    if mode == "checkpoint":
        await conn.execute(
            """INSERT INTO simulation_results
               (id, scenario_id, status, platform, pipeline_mode, created_at)
               VALUES ($1, $2, 'checkpoint:seed', $3, 'checkpoint', $4)""",
            result_id,
            scenario_id,
            sim_params_cp.platform,
            now,
        )
        await conn.execute(
            "UPDATE scenarios SET simulation_status = 'checkpoint', status = 'checkpoint', updated_at = $1 WHERE id = $2",
            now,
            scenario_id,
        )
        await ActionLogger.log(
            "simulation.start",
            scenario_id,
            payload={"result_id": result_id, "mode": "checkpoint"},
        )

        return {
            "scenario_id": scenario_id,
            "result_id": result_id,
            "status": "checkpoint:seed",
            "pipeline_mode": "checkpoint",
            "message": "Pipeline paused at seed review checkpoint",
        }

    if mode == "interactive":
        await conn.execute(
            """INSERT INTO simulation_results
               (id, scenario_id, status, platform, pipeline_mode, created_at)
               VALUES ($1, $2, 'generating_options', $3, 'interactive', $4)""",
            result_id,
            scenario_id,
            sim_params_cp.platform,
            now,
        )
        await conn.execute(
            "UPDATE scenarios SET simulation_status = 'simulating', status = 'simulating', updated_at = $1 WHERE id = $2",
            now,
            scenario_id,
        )

        sb_client = request.app.state.sb_client
        background_tasks.add_task(
            _generate_decision_options,
            scenario_id=scenario_id,
            result_id=result_id,
            sb_client=sb_client,
            bbox=json.loads(scenario["region_bbox"]),
            question=scenario["question"],
            region_name=scenario["region_name"],
            web_search_enabled=sim_params_cp.web_search_enabled,
        )
        await ActionLogger.log(
            "simulation.start",
            scenario_id,
            payload={"result_id": result_id, "mode": "interactive"},
        )

        return {
            "scenario_id": scenario_id,
            "result_id": result_id,
            "status": "generating_options",
            "pipeline_mode": "interactive",
            "message": "Generating AI decision options",
        }

    raw_params = scenario["simulation_params"] if "simulation_params" in scenario else "{}"
    sim_params = SimulationParams.model_validate_json(raw_params or "{}")

    mf_client = request.app.state.mf_client
    if not await mf_client.health_check():
        raise HTTPException(status_code=503, detail="MiroFish service unavailable")

    await conn.execute(
        """INSERT INTO simulation_results
           (id, scenario_id, status, platform, pipeline_mode, created_at)
           VALUES ($1, $2, 'starting', $3, 'auto', $4)""",
        result_id,
        scenario_id,
        sim_params.platform,
        now,
    )
    await conn.execute(
        "UPDATE scenarios SET simulation_status = 'simulating', status = 'simulating', updated_at = $1 WHERE id = $2",
        now,
        scenario_id,
    )

    orchestrator = SimulationOrchestrator(mf_client, sb_client=request.app.state.sb_client)
    background_tasks.add_task(
        orchestrator.run_pipeline,
        scenario_id=scenario_id,
        result_id=result_id,
        seed_text=seed_row["text"],
        max_rounds=scenario["max_rounds"],
        simulation_params=sim_params,
    )
    await ActionLogger.log(
        "simulation.start",
        scenario_id,
        payload={
            "result_id": result_id,
            "mode": "auto",
            "max_rounds": scenario["max_rounds"],
            "platform": sim_params.platform,
        },
    )

    return {
        "scenario_id": scenario_id,
        "result_id": result_id,
        "status": "starting",
        "pipeline_mode": "auto",
        "message": "Simulation pipeline started in background",
    }


@router.get("/{scenario_id}/checkpoint", response_model=CheckpointResponse)
async def get_checkpoint(
    scenario_id: str,
    conn: asyncpg.Connection = Depends(get_db),
):
    row = await conn.fetchrow(
        "SELECT * FROM simulation_results WHERE scenario_id = $1 ORDER BY created_at DESC LIMIT 1",
        scenario_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="No simulation found for this scenario")

    status = row["status"]
    if status not in CHECKPOINT_STEPS:
        raise HTTPException(
            status_code=400,
            detail=f"Not at a checkpoint (current status: {status})",
        )

    step_info = CHECKPOINT_STEPS[status]
    checkpoint_data = json.loads(row["checkpoint_data"]) if row["checkpoint_data"] else None

    if status == "checkpoint:seed":
        seed_row = await conn.fetchrow(
            "SELECT text FROM seeds WHERE scenario_id = $1 ORDER BY created_at DESC LIMIT 1",
            scenario_id,
        )
        checkpoint_data = {"seed_text": seed_row["text"]} if seed_row else None

    if status == "checkpoint:config":
        scn_row = await conn.fetchrow("SELECT max_rounds FROM scenarios WHERE id = $1", scenario_id)
        config = checkpoint_data or {}
        config["max_rounds"] = scn_row["max_rounds"] if scn_row else 10
        checkpoint_data = config

    if status == "checkpoint:decision":
        dp_rows = await conn.fetch(
            "SELECT id, type, status FROM decision_points WHERE scenario_id = $1 AND status = 'pending' ORDER BY created_at",
            scenario_id,
        )
        checkpoint_data = {
            "pending_decisions": [{"id": r["id"], "type": r["type"]} for r in dp_rows],
        }

    return CheckpointResponse(
        scenario_id=scenario_id,
        result_id=row["id"],
        status=status,
        step=step_info["step"],
        editable=step_info["editable"],
        data=checkpoint_data,
    )


@router.post("/{scenario_id}/retry", status_code=202)
async def retry_simulation(
    scenario_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    conn: asyncpg.Connection = Depends(get_db),
):
    row = await conn.fetchrow(
        "SELECT * FROM simulation_results WHERE scenario_id = $1 ORDER BY created_at DESC LIMIT 1",
        scenario_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="No simulation found for this scenario")

    if row["status"] != "failed":
        raise HTTPException(
            status_code=400,
            detail=f"Can only retry failed simulations (current status: {row['status']})",
        )

    mf_client = request.app.state.mf_client
    if not await mf_client.health_check():
        raise HTTPException(status_code=503, detail="MiroFish service unavailable")

    recovery_point = SimulationOrchestrator.determine_recovery_point(row)

    seed_row = await conn.fetchrow(
        "SELECT text FROM seeds WHERE scenario_id = $1 ORDER BY created_at DESC LIMIT 1",
        scenario_id,
    )
    if not seed_row:
        raise HTTPException(status_code=400, detail="Seed document not found")

    scn_row = await conn.fetchrow(
        "SELECT max_rounds, simulation_params FROM scenarios WHERE id = $1",
        scenario_id,
    )
    max_rounds = scn_row["max_rounds"] if scn_row else 10
    raw_params = scn_row["simulation_params"] if scn_row and "simulation_params" in scn_row else "{}"
    sim_params = SimulationParams.model_validate_json(raw_params or "{}")

    orchestrator = SimulationOrchestrator(mf_client, sb_client=request.app.state.sb_client)
    background_tasks.add_task(
        orchestrator.run_from_failure,
        scenario_id=scenario_id,
        result_id=row["id"],
        seed_text=seed_row["text"],
        max_rounds=max_rounds,
        recovery_point=recovery_point,
        project_id=row["mirofish_project_id"] or "",
        graph_id=row["graph_id"] or "",
        mf_simulation_id=row["mirofish_simulation_id"] or "",
        simulation_params=sim_params,
    )
    await ActionLogger.log(
        "simulation.retry",
        scenario_id,
        payload={
            "result_id": row["id"],
            "recovery_point": recovery_point,
        },
    )

    return {
        "scenario_id": scenario_id,
        "result_id": row["id"],
        "recovery_point": recovery_point,
        "message": f"Retrying from '{recovery_point}'",
    }


@router.post("/{scenario_id}/continue", status_code=202)
async def continue_pipeline(
    scenario_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    body: ContinueRequest | None = None,
    conn: asyncpg.Connection = Depends(get_db),
):
    row = await conn.fetchrow(
        "SELECT * FROM simulation_results WHERE scenario_id = $1 ORDER BY created_at DESC LIMIT 1",
        scenario_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="No simulation found for this scenario")

    status = row["status"]
    if status not in CHECKPOINT_STEPS:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot continue — not at a checkpoint (current status: {status})",
        )

    if row["pipeline_mode"] not in ("checkpoint", "interactive"):
        raise HTTPException(status_code=400, detail="Pipeline is not in checkpoint/interactive mode")

    if status == "checkpoint:decision":
        pending = await conn.fetch(
            "SELECT id, type FROM decision_points WHERE scenario_id = $1 AND status = 'pending'",
            scenario_id,
        )
        if pending:
            pending_types = [r["type"] for r in pending]
            raise HTTPException(
                status_code=400,
                detail=f"Unresolved decision points: {', '.join(pending_types)}",
            )

        seed_dp = await conn.fetchrow(
            "SELECT options, selected_option_id, custom_data FROM decision_points WHERE scenario_id = $1 AND type = 'seed_selection' AND status = 'resolved' ORDER BY resolved_at DESC LIMIT 1",
            scenario_id,
        )
        if seed_dp:
            if seed_dp["selected_option_id"] and seed_dp["options"]:
                options = json.loads(seed_dp["options"])
                selected = next((o for o in options if o["id"] == seed_dp["selected_option_id"]), None)
                if selected and selected.get("data", {}).get("seed_text"):
                    await conn.execute(
                        "UPDATE seeds SET text = $1 WHERE scenario_id = $2 AND id = (SELECT id FROM seeds WHERE scenario_id = $3 ORDER BY created_at DESC LIMIT 1)",
                        selected["data"]["seed_text"], scenario_id, scenario_id,
                    )
            elif seed_dp["custom_data"]:
                custom = json.loads(seed_dp["custom_data"])
                if custom.get("seed_text"):
                    await conn.execute(
                        "UPDATE seeds SET text = $1 WHERE scenario_id = $2 AND id = (SELECT id FROM seeds WHERE scenario_id = $3 ORDER BY created_at DESC LIMIT 1)",
                        custom["seed_text"], scenario_id, scenario_id,
                    )

        param_dp = await conn.fetchrow(
            "SELECT options, selected_option_id, custom_data FROM decision_points WHERE scenario_id = $1 AND type = 'parameter_recommendation' AND status = 'resolved' ORDER BY resolved_at DESC LIMIT 1",
            scenario_id,
        )
        if param_dp:
            params_data = None
            if param_dp["selected_option_id"] and param_dp["options"]:
                options = json.loads(param_dp["options"])
                selected = next((o for o in options if o["id"] == param_dp["selected_option_id"]), None)
                if selected:
                    params_data = selected.get("data", {})
            elif param_dp["custom_data"]:
                params_data = json.loads(param_dp["custom_data"])

            if params_data:
                if "max_rounds" in params_data:
                    await conn.execute(
                        "UPDATE scenarios SET max_rounds = $1 WHERE id = $2",
                        int(params_data["max_rounds"]), scenario_id,
                    )
                sim_update_fields = {}
                for key in ("platform", "simulation_hours", "geopolitics_enabled", "web_search_enabled"):
                    if key in params_data:
                        sim_update_fields[key] = params_data[key]
                if sim_update_fields:
                    scn = await conn.fetchrow("SELECT simulation_params FROM scenarios WHERE id = $1", scenario_id)
                    current_params = json.loads(scn["simulation_params"]) if scn and scn["simulation_params"] else {}
                    current_params.update(sim_update_fields)
                    await conn.execute(
                        "UPDATE scenarios SET simulation_params = $1 WHERE id = $2",
                        json.dumps(current_params), scenario_id,
                    )

        await conn.execute(
            "UPDATE simulation_results SET status = 'checkpoint:seed', pipeline_mode = 'checkpoint' WHERE id = $1",
            row["id"],
        )
        await ActionLogger.log(
            "decision.applied", scenario_id,
            payload={"result_id": row["id"]},
        )

    mf_client = request.app.state.mf_client
    if status != "checkpoint:profiles" and not await mf_client.health_check():
        raise HTTPException(status_code=503, detail="MiroFish service unavailable")

    scn_row = await conn.fetchrow("SELECT max_rounds, simulation_params FROM scenarios WHERE id = $1", scenario_id)
    max_rounds = scn_row["max_rounds"] if scn_row else 10
    raw_params = scn_row["simulation_params"] if scn_row and "simulation_params" in scn_row else "{}"
    sim_params = SimulationParams.model_validate_json(raw_params or "{}")

    orchestrator = SimulationOrchestrator(mf_client, sb_client=request.app.state.sb_client)
    edits = body.edits if body else None

    background_tasks.add_task(
        orchestrator.run_from_checkpoint,
        scenario_id=scenario_id,
        result_id=row["id"],
        max_rounds=max_rounds,
        edits=edits,
        simulation_params=sim_params,
    )
    await ActionLogger.log(
        "simulation.continue",
        scenario_id,
        payload={"result_id": row["id"], "from_status": status},
    )

    return {
        "scenario_id": scenario_id,
        "result_id": row["id"],
        "previous_status": status,
        "message": "Continuing pipeline from checkpoint",
    }


@router.get("/{scenario_id}/status")
async def get_simulation_status(
    scenario_id: str,
    conn: asyncpg.Connection = Depends(get_db),
):
    """시뮬레이션 파이프라인 현재 상태를 조회한다."""
    row = await conn.fetchrow(
        "SELECT * FROM simulation_results WHERE scenario_id = $1 ORDER BY created_at DESC LIMIT 1",
        scenario_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="No simulation found for this scenario")

    result = {
        "scenario_id": scenario_id,
        "result_id": row["id"],
        "status": row["status"],
        "mirofish_project_id": row["mirofish_project_id"],
        "mirofish_simulation_id": row["mirofish_simulation_id"],
        "created_at": row["created_at"],
        "completed_at": row["completed_at"],
    }

    if row["status"] == "failed":
        error_row = await conn.fetchrow(
            """SELECT payload FROM action_log
               WHERE scenario_id = $1 AND action_type = 'pipeline.failed'
               ORDER BY created_at DESC LIMIT 1""",
            scenario_id,
        )
        if error_row and error_row["payload"]:
            payload = json.loads(error_row["payload"])
            result["error_message"] = payload.get("error", "")

    return result


@router.get("/{scenario_id}/results", response_model=SimulationResultResponse)
async def get_simulation_results(
    scenario_id: str,
    conn: asyncpg.Connection = Depends(get_db),
):
    """시뮬레이션 결과를 조회한다."""
    row = await conn.fetchrow(
        "SELECT * FROM simulation_results WHERE scenario_id = $1 ORDER BY created_at DESC LIMIT 1",
        scenario_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="No simulation found for this scenario")

    if row["status"] != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Simulation not completed yet (status: {row['status']})",
        )

    return SimulationResultResponse(
        id=row["id"],
        scenario_id=row["scenario_id"],
        mirofish_simulation_id=row["mirofish_simulation_id"],
        mirofish_project_id=row["mirofish_project_id"],
        status=row["status"],
        platform=row["platform"],
        results=json.loads(row["results"]) if row["results"] else None,
        geojson=json.loads(row["geojson"]) if row["geojson"] else None,
        report=row["report"],
        created_at=row["created_at"],
        completed_at=row["completed_at"],
    )


@router.get("/{scenario_id}/geojson")
async def get_geojson(
    scenario_id: str,
    conn: asyncpg.Connection = Depends(get_db),
):
    """시뮬레이션 결과를 GeoJSON FeatureCollection으로 반환한다."""
    from app.services.result_projector import ResultProjector

    row = await conn.fetchrow(
        "SELECT * FROM simulation_results WHERE scenario_id = $1 ORDER BY created_at DESC LIMIT 1",
        scenario_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="No simulation found for this scenario")

    if row["status"] != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Simulation not completed yet (status: {row['status']})",
        )

    if row["geojson"]:
        return json.loads(row["geojson"])

    results = json.loads(row["results"]) if row["results"] else {}

    scn = await conn.fetchrow("SELECT region_bbox FROM scenarios WHERE id = $1", scenario_id)
    fallback = None
    if scn:
        bbox = json.loads(scn["region_bbox"])
        fallback = ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)

    projector = ResultProjector()
    geojson = projector.project_to_geojson(results, fallback_center=fallback)

    await conn.execute(
        "UPDATE simulation_results SET geojson = $1 WHERE id = $2",
        json.dumps(geojson, ensure_ascii=False),
        row["id"],
    )

    return geojson


@router.get("/{scenario_id}/report")
async def get_report(
    scenario_id: str,
    conn: asyncpg.Connection = Depends(get_db),
):
    """MiroFish 시뮬레이션 보고서를 반환한다."""
    row = await conn.fetchrow(
        "SELECT * FROM simulation_results WHERE scenario_id = $1 ORDER BY created_at DESC LIMIT 1",
        scenario_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="No simulation found for this scenario")

    if row["status"] != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Simulation not completed yet (status: {row['status']})",
        )

    return {
        "scenario_id": scenario_id,
        "report": row["report"] or "",
        "completed_at": row["completed_at"],
    }


async def _get_sim_row(conn: asyncpg.Connection, scenario_id: str) -> asyncpg.Record:
    """시나리오의 최신 simulation_results 행을 반환. 없으면 404."""
    row = await conn.fetchrow(
        "SELECT * FROM simulation_results WHERE scenario_id = $1 ORDER BY created_at DESC LIMIT 1",
        scenario_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="No simulation found for this scenario")
    return row


@router.get("/{scenario_id}/live/stats")
async def get_live_stats(
    scenario_id: str,
    request: Request,
    conn: asyncpg.Connection = Depends(get_db),
):
    """실시간 시뮬레이션 실행 상태 (run-status 프록시)."""
    row = await _get_sim_row(conn, scenario_id)
    mf_sim_id = row["mirofish_simulation_id"]
    if not mf_sim_id:
        return {"status": row["status"], "message": "MiroFish simulation not yet created"}

    mf_client = request.app.state.mf_client
    try:
        return await mf_client.get_run_status(mf_sim_id)
    except Exception:
        return {"status": row["status"], "message": "MiroFish unavailable"}


@router.get("/{scenario_id}/live/actions")
async def get_live_actions(
    scenario_id: str,
    request: Request,
    offset: int = 0,
    limit: int = 100,
    platform: str = "twitter",
    conn: asyncpg.Connection = Depends(get_db),
):
    """실시간 에이전트 액션 목록 (offset 기반 incremental)."""
    row = await _get_sim_row(conn, scenario_id)
    mf_sim_id = row["mirofish_simulation_id"]
    if not mf_sim_id:
        return {"actions": [], "count": 0}

    mf_client = request.app.state.mf_client
    try:
        return await mf_client.get_simulation_actions(
            mf_sim_id,
            platform=platform,
            limit=limit,
            offset=offset,
        )
    except Exception as e:
        logger.exception("Failed to fetch live actions for scenario %s", scenario_id)
        raise HTTPException(status_code=502, detail="Upstream service error") from e


@router.get("/{scenario_id}/live/graph_task")
async def get_live_graph_task(
    scenario_id: str,
    request: Request,
    conn: asyncpg.Connection = Depends(get_db),
):
    """그래프 빌드 태스크 진행률."""
    row = await _get_sim_row(conn, scenario_id)
    task_id = row["graph_task_id"]
    if not task_id:
        return {"status": row["status"], "message": "Graph build not started"}

    mf_client = request.app.state.mf_client
    try:
        return await mf_client.get_task_status(task_id)
    except Exception as e:
        logger.exception("Failed to fetch live graph task for scenario %s", scenario_id)
        raise HTTPException(status_code=502, detail="Upstream service error") from e


@router.get("/{scenario_id}/live/graph_data")
async def get_live_graph_data(
    scenario_id: str,
    request: Request,
    conn: asyncpg.Connection = Depends(get_db),
):
    """그래프 노드+엣지 데이터 (빌드 중에도 호출 가능)."""
    row = await _get_sim_row(conn, scenario_id)
    graph_id = row["graph_id"]
    if not graph_id:
        return {"nodes": [], "edges": [], "node_count": 0, "edge_count": 0}

    mf_client = request.app.state.mf_client
    try:
        return await mf_client.get_graph_data(graph_id)
    except Exception as e:
        logger.exception("Failed to fetch live graph data for scenario %s", scenario_id)
        raise HTTPException(status_code=502, detail="Upstream service error") from e


@router.get("/{scenario_id}/live/profiles")
async def get_live_profiles(
    scenario_id: str,
    request: Request,
    platform: str = "twitter",
    conn: asyncpg.Connection = Depends(get_db),
):
    """프로필 생성 실시간 진행."""
    row = await _get_sim_row(conn, scenario_id)
    mf_sim_id = row["mirofish_simulation_id"]
    if not mf_sim_id:
        return {"count": 0, "total_expected": 0, "is_generating": False, "profiles": []}

    mf_client = request.app.state.mf_client
    try:
        return await mf_client.get_profiles_realtime(mf_sim_id, platform=platform)
    except Exception:
        return {"count": 0, "total_expected": 0, "is_generating": False, "profiles": []}


@router.get("/{scenario_id}/live/config")
async def get_live_config(
    scenario_id: str,
    request: Request,
    conn: asyncpg.Connection = Depends(get_db),
):
    """설정 생성 실시간 진행."""
    row = await _get_sim_row(conn, scenario_id)
    mf_sim_id = row["mirofish_simulation_id"]
    if not mf_sim_id:
        return {"file_exists": False, "is_generating": False}

    mf_client = request.app.state.mf_client
    try:
        return await mf_client.get_config_realtime(mf_sim_id)
    except Exception:
        return {"file_exists": False, "is_generating": False}


@router.get("/{scenario_id}/snapshot")
async def get_snapshot_metadata(
    scenario_id: str,
    conn: asyncpg.Connection = Depends(get_db),
):
    row = await conn.fetchrow(
        """SELECT id, scenario_id, snapshot_at, created_at,
                  length(fast_data) as fast_size, length(slow_data) as slow_size
           FROM scenario_snapshots WHERE scenario_id = $1
           ORDER BY created_at DESC LIMIT 1""",
        scenario_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="No snapshot found for this scenario")
    return {
        "id": row["id"],
        "scenario_id": row["scenario_id"],
        "snapshot_at": row["snapshot_at"],
        "fast_data_size_bytes": row["fast_size"] or 0,
        "slow_data_size_bytes": row["slow_size"] or 0,
    }


@router.get("/{scenario_id}/snapshot/data")
async def get_snapshot_data(
    scenario_id: str,
    source: str = "fast",
    conn: asyncpg.Connection = Depends(get_db),
):
    if source not in ("fast", "slow"):
        raise HTTPException(status_code=400, detail="source must be fast or slow")

    col = "slow_data" if source == "slow" else "fast_data"
    row = await conn.fetchrow(
        f"SELECT {col} FROM scenario_snapshots WHERE scenario_id = $1 ORDER BY created_at DESC LIMIT 1",
        scenario_id,
    )
    if not row or not row[col]:
        raise HTTPException(status_code=404, detail="No snapshot found")
    return json.loads(row[col])


@router.get("/{scenario_id}/audit")
async def get_audit_log(
    scenario_id: str,
    action_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
    db: asyncpg.Connection = Depends(get_db),
):
    del db
    events = await ActionLogger.query(
        scenario_id=scenario_id,
        action_type=action_type,
        limit=limit,
        offset=offset,
    )
    return {"scenario_id": scenario_id, "count": len(events), "events": events}


@router.get("/{scenario_id}/observations")
async def get_scenario_observations(
    scenario_id: str,
    limit: int = 100,
    offset: int = 0,
    conn: asyncpg.Connection = Depends(get_db),
):
    rows = await conn.fetch(
        """SELECT so.id, so.observation_id, so.used_in_seed, so.created_at,
                  o.source_type, o.source_id, o.observed_at
           FROM scenario_observations so
           LEFT JOIN observations o ON o.id = so.observation_id
           WHERE so.scenario_id = $1
           ORDER BY so.created_at DESC
           LIMIT $2 OFFSET $3""",
        scenario_id, limit, offset,
    )
    return {
        "scenario_id": scenario_id,
        "count": len(rows),
        "observations": [
            {
                "id": r["id"],
                "observation_id": r["observation_id"],
                "source_type": r["source_type"],
                "source_id": r["source_id"],
                "used_in_seed": r["used_in_seed"],
                "observed_at": r["observed_at"],
                "created_at": r["created_at"],
            }
            for r in rows
        ],
    }


@router.get("/{scenario_id}/geopolitics")
async def get_geopolitics_summary(
    scenario_id: str,
    conn: asyncpg.Connection = Depends(get_db),
):
    count = await conn.fetchval(
        "SELECT COUNT(*) FROM geopolitics_events WHERE scenario_id = $1",
        scenario_id,
    )
    actors = await conn.fetch(
        "SELECT DISTINCT actor_id FROM geopolitics_events WHERE scenario_id = $1",
        scenario_id,
    )
    max_round = await conn.fetchval(
        "SELECT MAX(round_number) FROM geopolitics_events WHERE scenario_id = $1",
        scenario_id,
    )
    return {
        "scenario_id": scenario_id,
        "total_events": count or 0,
        "total_rounds": max_round or 0,
        "actors": [r["actor_id"] for r in actors],
    }


@router.get("/{scenario_id}/geopolitics/events")
async def get_geopolitics_events(
    scenario_id: str,
    limit: int = 100,
    offset: int = 0,
    conn: asyncpg.Connection = Depends(get_db),
):
    rows = await conn.fetch(
        """SELECT * FROM geopolitics_events
           WHERE scenario_id = $1
           ORDER BY round_number, event_at
           LIMIT $2 OFFSET $3""",
        scenario_id, limit, offset,
    )
    return {
        "scenario_id": scenario_id,
        "count": len(rows),
        "events": [
            {
                "id": r["id"],
                "action_type": r["action_type"],
                "actor_id": r["actor_id"],
                "target_actor_ids": json.loads(r["target_actor_ids"]) if r["target_actor_ids"] else [],
                "content": r["content"],
                "magnitude": r["magnitude"],
                "round_number": r["round_number"],
                "event_at": r["event_at"],
            }
            for r in rows
        ],
    }


@router.get("/{scenario_id}/geopolitics/timeline")
async def get_geopolitics_timeline(
    scenario_id: str,
    conn: asyncpg.Connection = Depends(get_db),
):
    rows = await conn.fetch(
        """SELECT round_number, action_type, actor_id, target_actor_ids, content, magnitude
           FROM geopolitics_events
           WHERE scenario_id = $1
           ORDER BY round_number, event_at""",
        scenario_id,
    )
    rounds: dict[int, list[dict]] = {}
    for r in rows:
        rn = r["round_number"]
        rounds.setdefault(rn, []).append({
            "action_type": r["action_type"],
            "actor_id": r["actor_id"],
            "target_actor_ids": json.loads(r["target_actor_ids"]) if r["target_actor_ids"] else [],
            "content": r["content"],
            "magnitude": r["magnitude"],
        })
    return {
        "scenario_id": scenario_id,
        "timeline": [{"round": rn, "events": evts} for rn, evts in sorted(rounds.items())],
    }


# ── Decision Points (V4-1) ──


def _row_to_decision_point(row: asyncpg.Record) -> DecisionPointResponse:
    return DecisionPointResponse(
        id=row["id"],
        scenario_id=row["scenario_id"],
        type=row["type"],
        options=[DecisionOption(**o) for o in json.loads(row["options"])],
        recommended=row["recommended"],
        allow_custom=row["allow_custom"],
        status=row["status"],
        selected_option_id=row["selected_option_id"],
        custom_data=json.loads(row["custom_data"]) if row["custom_data"] else None,
        created_at=row["created_at"],
        resolved_at=row["resolved_at"],
    )


@router.post(
    "/{scenario_id}/decision_points",
    response_model=DecisionPointResponse,
    status_code=201,
)
async def create_decision_point(
    scenario_id: str,
    body: DecisionPointCreate,
    conn: asyncpg.Connection = Depends(get_db),
):
    scenario = await conn.fetchrow("SELECT id FROM scenarios WHERE id = $1", scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    option_ids = {o.id for o in body.options}
    if body.recommended not in option_ids:
        raise HTTPException(
            status_code=400,
            detail=f"recommended '{body.recommended}' not found in options",
        )

    dp_id = f"dp_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()

    await conn.execute(
        """INSERT INTO decision_points
           (id, scenario_id, type, options, recommended, allow_custom, status, created_at)
           VALUES ($1, $2, $3, $4, $5, $6, 'pending', $7)""",
        dp_id,
        scenario_id,
        body.type.value,
        json.dumps([o.model_dump() for o in body.options], ensure_ascii=False),
        body.recommended,
        body.allow_custom,
        now,
    )
    await ActionLogger.log(
        "decision_point.create",
        scenario_id,
        payload={"dp_id": dp_id, "type": body.type.value, "options_count": len(body.options)},
    )

    row = await conn.fetchrow("SELECT * FROM decision_points WHERE id = $1", dp_id)
    if not row:
        raise HTTPException(status_code=500, detail="Failed to read back created decision point")
    return _row_to_decision_point(row)


@router.get("/{scenario_id}/decision_points")
async def list_decision_points(
    scenario_id: str,
    status: str | None = None,
    conn: asyncpg.Connection = Depends(get_db),
):
    scenario = await conn.fetchrow("SELECT id FROM scenarios WHERE id = $1", scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    if status:
        rows = await conn.fetch(
            "SELECT * FROM decision_points WHERE scenario_id = $1 AND status = $2 ORDER BY created_at DESC",
            scenario_id,
            status,
        )
    else:
        rows = await conn.fetch(
            "SELECT * FROM decision_points WHERE scenario_id = $1 ORDER BY created_at DESC",
            scenario_id,
        )

    return {
        "scenario_id": scenario_id,
        "count": len(rows),
        "decision_points": [_row_to_decision_point(r) for r in rows],
    }


@router.get(
    "/{scenario_id}/decision_points/{dp_id}",
    response_model=DecisionPointResponse,
)
async def get_decision_point(
    scenario_id: str,
    dp_id: str,
    conn: asyncpg.Connection = Depends(get_db),
):
    row = await conn.fetchrow(
        "SELECT * FROM decision_points WHERE id = $1 AND scenario_id = $2",
        dp_id,
        scenario_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Decision point not found")
    return _row_to_decision_point(row)


@router.post(
    "/{scenario_id}/decision_points/{dp_id}/resolve",
    response_model=DecisionPointResponse,
)
async def resolve_decision_point(
    scenario_id: str,
    dp_id: str,
    body: DecisionPointResolveRequest,
    conn: asyncpg.Connection = Depends(get_db),
):
    row = await conn.fetchrow(
        "SELECT * FROM decision_points WHERE id = $1 AND scenario_id = $2",
        dp_id,
        scenario_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Decision point not found")

    if row["status"] == "resolved":
        raise HTTPException(status_code=409, detail="Decision point already resolved")

    if not body.selected_option_id and not body.custom_data:
        raise HTTPException(
            status_code=400,
            detail="Either selected_option_id or custom_data is required",
        )

    if body.selected_option_id:
        options = json.loads(row["options"])
        option_ids = {o["id"] for o in options}
        if body.selected_option_id not in option_ids:
            raise HTTPException(
                status_code=400,
                detail=f"selected_option_id '{body.selected_option_id}' not found in options",
            )

    if not body.selected_option_id and body.custom_data and not row["allow_custom"]:
        raise HTTPException(
            status_code=400,
            detail="Custom data not allowed for this decision point",
        )

    now = datetime.now(timezone.utc).isoformat()
    custom_json = json.dumps(body.custom_data, ensure_ascii=False) if body.custom_data else None

    await conn.execute(
        """UPDATE decision_points
           SET status = 'resolved', selected_option_id = $1, custom_data = $2, resolved_at = $3
           WHERE id = $4""",
        body.selected_option_id,
        custom_json,
        now,
        dp_id,
    )
    await ActionLogger.log(
        "decision_point.resolve",
        scenario_id,
        payload={
            "dp_id": dp_id,
            "selected_option_id": body.selected_option_id,
            "has_custom_data": body.custom_data is not None,
        },
    )

    updated = await conn.fetchrow("SELECT * FROM decision_points WHERE id = $1", dp_id)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to read back resolved decision point")
    return _row_to_decision_point(updated)


@router.post("/{scenario_id}/briefing/generate", status_code=201)
async def generate_briefing(
    scenario_id: str,
    conn: asyncpg.Connection = Depends(get_db),
):
    scenario = await conn.fetchrow(
        "SELECT id, simulation_status FROM scenarios WHERE id = $1",
        scenario_id,
    )
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    if scenario["simulation_status"] != "completed":
        raise HTTPException(status_code=400, detail="Simulation must be completed first")

    from app.services.briefing_generator import BriefingGenerator

    generator = BriefingGenerator()
    try:
        briefing = await generator.generate(scenario_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception:
        logger.exception("Briefing generation failed for scenario %s", scenario_id)
        raise HTTPException(status_code=500, detail="Briefing generation failed")

    return briefing


@router.get("/{scenario_id}/briefing")
async def get_briefing(
    scenario_id: str,
    conn: asyncpg.Connection = Depends(get_db),
):
    row = await conn.fetchrow(
        """SELECT id, scenario_id, content, version, created_at, updated_at
           FROM briefings
           WHERE scenario_id = $1
           ORDER BY version DESC, created_at DESC
           LIMIT 1""",
        scenario_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Briefing not found for this scenario")

    return {
        "id": row["id"],
        "scenario_id": row["scenario_id"],
        "content": row["content"],
        "version": row["version"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


@router.put("/{scenario_id}/briefing")
async def update_briefing(
    scenario_id: str,
    request: Request,
    conn: asyncpg.Connection = Depends(get_db),
):
    body = await request.json()
    content = body.get("content") if isinstance(body, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise HTTPException(status_code=400, detail="content is required")

    now = datetime.now(timezone.utc).isoformat()
    updated = await conn.fetchrow(
        """UPDATE briefings
           SET content = $1, version = version + 1, updated_at = $2
           WHERE id = (
               SELECT id FROM briefings
               WHERE scenario_id = $3
               ORDER BY version DESC, created_at DESC
               LIMIT 1
           )
           RETURNING id, scenario_id, content, version, created_at, updated_at""",
        content,
        now,
        scenario_id,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Briefing not found for this scenario")

    return {
        "id": updated["id"],
        "scenario_id": updated["scenario_id"],
        "content": updated["content"],
        "version": updated["version"],
        "created_at": updated["created_at"],
        "updated_at": updated["updated_at"],
    }


# ── Export ──


@router.get("/{scenario_id}/export")
async def export_scenario(
    scenario_id: str,
    format: str = "json",
    conn: asyncpg.Connection = Depends(get_db),
):
    scenario = await conn.fetchrow("SELECT id, name FROM scenarios WHERE id = $1", scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    from app.services.data_exporter import DataExporter

    exporter = DataExporter()

    if format == "csv":
        csv_data = await exporter.export_actions_csv(scenario_id)
        if not csv_data:
            raise HTTPException(status_code=404, detail="No simulation actions to export")
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{scenario["name"]}_actions.csv"'},
        )

    data = await exporter.export_scenario_json(scenario_id)
    return JSONResponse(
        content=data,
        headers={"Content-Disposition": f'attachment; filename="{scenario["name"]}.json"'},
    )


@router.get("/{scenario_id}/export/observations")
async def export_observations(
    scenario_id: str,
    conn: asyncpg.Connection = Depends(get_db),
):
    scenario = await conn.fetchrow("SELECT id, name FROM scenarios WHERE id = $1", scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    from app.services.data_exporter import DataExporter

    csv_data = await DataExporter().export_observations_csv(scenario_id)
    if not csv_data:
        raise HTTPException(status_code=404, detail="No observations to export")
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{scenario["name"]}_observations.csv"'},
    )


@router.get("/{scenario_id}/export/geopolitics")
async def export_geopolitics(
    scenario_id: str,
    conn: asyncpg.Connection = Depends(get_db),
):
    scenario = await conn.fetchrow("SELECT id, name FROM scenarios WHERE id = $1", scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    from app.services.data_exporter import DataExporter

    csv_data = await DataExporter().export_geopolitics_csv(scenario_id)
    if not csv_data:
        raise HTTPException(status_code=404, detail="No geopolitics events to export")
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{scenario["name"]}_geopolitics.csv"'},
    )


@router.get("/{scenario_id}/export/report")
async def export_report(
    scenario_id: str,
    conn: asyncpg.Connection = Depends(get_db),
):
    scenario = await conn.fetchrow("SELECT id, name FROM scenarios WHERE id = $1", scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    from app.services.data_exporter import DataExporter

    md = await DataExporter().export_report_markdown(scenario_id)
    if not md:
        raise HTTPException(status_code=404, detail="No report available")
    return PlainTextResponse(
        content=md,
        headers={"Content-Disposition": f'attachment; filename="{scenario["name"]}_report.md"'},
    )


# ── Interactive Simulation ──


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
    conn: asyncpg.Connection = Depends(get_db),
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
    request: Request,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    conn: asyncpg.Connection = Depends(get_db),
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

    mf_client = request.app.state.mf_client
    orchestrator = SimulationOrchestrator(mf_client, sb_client=request.app.state.sb_client)
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


# ── What-If Counterfactual Replay ──


@router.post("/{scenario_id}/simulation/whatif", status_code=201)
async def create_whatif_branch(
    scenario_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    conn: asyncpg.Connection = Depends(get_db),
):
    body = await request.json()

    from app.models.interactive import WhatIfCreateRequest
    from app.services.whatif_engine import WhatIfEngine

    req = WhatIfCreateRequest(**body)

    mf_client = request.app.state.mf_client
    sb_client = getattr(request.app.state, "sb_client", None)
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
    request: Request,
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

    mf_client = request.app.state.mf_client
    sb_client = getattr(request.app.state, "sb_client", None)
    engine = WhatIfEngine(mf_client, sb_client)

    try:
        comparison = await engine.compare(branch_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return comparison.model_dump()
