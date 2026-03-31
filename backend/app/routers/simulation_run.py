import json
import logging
import uuid
from datetime import datetime, timezone

import asyncpg
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import JSONResponse

from app.clients.mirofish import MiroFishClient
from app.clients.shadowbroker import ShadowBrokerClient
from app.database import get_db, get_pool
from app.models.decision_point import DecisionOption, DecisionPointResponse
from app.models.result import (
    CheckpointResponse,
    ContinueRequest,
    SimulateRequest,
    SimulationResultResponse,
)
from app.models.scenario import SimulationParams
from app.routers._helpers import get_mf_client, get_sb_client, row_to_decision_point
from app.services.action_logger import ActionLogger
from app.services.param_recommender import recommend_params
from app.services.seed_generator import SeedGenerator
from app.services.simulation_orchestrator import SimulationOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scenario", tags=["simulation-run"])


CHECKPOINT_STEPS = {
    "checkpoint:seed": {"step": "seed", "editable": True},
    "checkpoint:ontology": {"step": "ontology", "editable": False},
    "checkpoint:graph": {"step": "graph", "editable": False},
    "checkpoint:profiles": {"step": "profiles", "editable": False},
    "checkpoint:config": {"step": "config", "editable": True},
    "checkpoint:geopolitics": {"step": "geopolitics", "editable": False},
    "checkpoint:decision": {"step": "decision", "editable": True},
    "simulating:geopolitics_paused": {"step": "geopolitics_interactive", "editable": True},
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
    background_tasks: BackgroundTasks,
    body: SimulateRequest | None = None,
    mf_client: MiroFishClient = Depends(get_mf_client),
    sb_client: ShadowBrokerClient = Depends(get_sb_client),
):
    """시뮬레이션 파이프라인을 시작한다.

    mode="auto": 기존 동작 (전부 자동, 백그라운드 실행)
    mode="checkpoint": 첫 체크포인트(시드 검토)에서 일시정지

    NOTE: get_db_tx 대신 수동 트랜잭션을 사용한다.
    Starlette는 백그라운드 태스크 완료 후에야 의존성을 정리하므로,
    get_db_tx를 쓰면 INSERT가 커밋되기 전에 백그라운드 태스크가
    같은 row를 UPDATE하려 해서 데드락이 발생한다.
    """
    mode = (body.mode if body else "auto") or "auto"
    if mode not in ("auto", "checkpoint", "interactive"):
        raise HTTPException(status_code=400, detail="mode must be 'auto', 'checkpoint', or 'interactive'")

    pool = get_pool()
    async with pool.acquire() as conn:
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
            async with conn.transaction():
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
            async with conn.transaction():
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

        if not await mf_client.health_check():
            raise HTTPException(status_code=503, detail="MiroFish service unavailable")

        async with conn.transaction():
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
        orchestrator = SimulationOrchestrator(mf_client, sb_client=sb_client)
        run_method = orchestrator.run_wargame_pipeline if sim_params.wargame_enabled else orchestrator.run_pipeline
        background_tasks.add_task(
            run_method,
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
    background_tasks: BackgroundTasks,
    mf_client: MiroFishClient = Depends(get_mf_client),
    sb_client: ShadowBrokerClient = Depends(get_sb_client),
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

    orchestrator = SimulationOrchestrator(mf_client, sb_client=sb_client)
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
    background_tasks: BackgroundTasks,
    body: ContinueRequest | None = None,
    mf_client: MiroFishClient = Depends(get_mf_client),
    sb_client: ShadowBrokerClient = Depends(get_sb_client),
):
    """NOTE: start_simulation과 같은 이유로 get_db_tx 대신 수동 트랜잭션 사용.
    백그라운드 태스크가 미커밋 row를 UPDATE하려 해서 데드락 발생 방지.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM simulation_results WHERE scenario_id = $1 ORDER BY created_at DESC LIMIT 1",
            scenario_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="No simulation found for this scenario")

        status = row["status"]
        if status.startswith("wargame:paused:round_"):
            pending = await conn.fetch(
                "SELECT id FROM decision_points WHERE scenario_id = $1 AND status = 'pending' AND type IN ('geopolitics_actor_response', 'geopolitics_direction')",
                scenario_id,
            )
            if pending:
                raise HTTPException(status_code=400, detail="Unresolved wargame decision points")

            scn_row_wg = await conn.fetchrow("SELECT simulation_params FROM scenarios WHERE id = $1", scenario_id)
            raw_params_wg = scn_row_wg["simulation_params"] if scn_row_wg and "simulation_params" in scn_row_wg else "{}"
            sim_params_wg = SimulationParams.model_validate_json(raw_params_wg or "{}")

            orchestrator = SimulationOrchestrator(mf_client, sb_client=sb_client)
            background_tasks.add_task(
                orchestrator.continue_wargame,
                scenario_id=scenario_id,
                result_id=row["id"],
                simulation_params=sim_params_wg,
            )
            await ActionLogger.log(
                "simulation.wargame_continue",
                scenario_id,
                payload={"result_id": row["id"], "from_status": status},
            )
            return {
                "scenario_id": scenario_id,
                "result_id": row["id"],
                "previous_status": status,
                "message": "Continuing wargame pipeline",
            }

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

        if status == "simulating:geopolitics_paused":
            pending = await conn.fetch(
                "SELECT id FROM decision_points WHERE scenario_id = $1 AND status = 'pending' AND type IN ('geopolitics_actor_response', 'geopolitics_direction')",
                scenario_id,
            )
            if pending:
                raise HTTPException(status_code=400, detail="Unresolved geopolitics decision points")

            snapshot = await conn.fetchrow(
                "SELECT * FROM geopolitics_snapshots WHERE scenario_id = $1 AND result_id = $2 ORDER BY round_number DESC LIMIT 1",
                scenario_id, row["id"],
            )
            if not snapshot:
                raise HTTPException(status_code=400, detail="No geopolitics snapshot found")

            dp_row = await conn.fetchrow(
                "SELECT type, options, selected_option_id, custom_data FROM decision_points WHERE id = $1 AND status = 'resolved'",
                snapshot["pending_decision_point_id"],
            )
            if not dp_row:
                raise HTTPException(status_code=400, detail="Decision point not resolved")

            from app.geopolitics.engine import DecisionEngine
            from app.models.scenario import GeopoliticsMode

            engine_state = json.loads(snapshot["engine_state"])
            engine = DecisionEngine.from_state(engine_state)
            mode = GeopoliticsMode(snapshot["geopolitics_mode"])

            if mode == GeopoliticsMode.ACTOR_ROLE:
                selected_action = dp_row["selected_option_id"]
                if selected_action and snapshot["player_actor_id"]:
                    engine.override_next_action(snapshot["player_actor_id"], selected_action)
            elif mode == GeopoliticsMode.GAME_MASTER:
                options = json.loads(dp_row["options"])
                selected = next((o for o in options if o["id"] == dp_row["selected_option_id"]), None)
                if selected and selected.get("data"):
                    deltas = selected["data"].get("state_deltas", {})
                    applies_to = selected["data"].get("applies_to", "all")
                    engine.apply_direction_deltas(deltas, applies_to)

            scn_row_geo = await conn.fetchrow("SELECT simulation_params FROM scenarios WHERE id = $1", scenario_id)
            raw_params_geo = scn_row_geo["simulation_params"] if scn_row_geo else "{}"
            sim_params_geo = SimulationParams.model_validate_json(raw_params_geo or "{}")
            remaining_rounds = sim_params_geo.geopolitics_rounds - snapshot["round_number"]

            now = datetime.now(timezone.utc).isoformat()
            for _ in range(remaining_rounds):
                round_result = engine.run_single_round()
                for event_dict in round_result.get("events", []) + round_result.get("cascade_events", []):
                    event_id = f"ge_{uuid.uuid4().hex[:12]}"
                    await conn.execute(
                        """INSERT INTO geopolitics_events
                           (id, scenario_id, simulation_result_id, action_type, actor_id,
                            target_actor_ids, content, magnitude, round_number, event_at)
                           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)""",
                        event_id, scenario_id, row["id"],
                        event_dict.get("event_type", ""),
                        event_dict.get("source_actor_id", ""),
                        json.dumps(event_dict.get("target_actor_ids", [])),
                        event_dict.get("description", ""),
                        event_dict.get("magnitude", 0.5),
                        event_dict.get("round_number", 0),
                        now,
                    )

                from app.services.geopolitics_interactive import should_pause, build_actor_response_options, build_direction_options, find_trigger_event, save_geopolitics_snapshot, create_geopolitics_decision_point, link_snapshot_to_dp

                if should_pause(round_result, mode, sim_params_geo.geopolitics_player_actor_id, sim_params_geo.geopolitics_pause_threshold):
                    snap_id = await save_geopolitics_snapshot(
                        scenario_id, row["id"], snapshot["round_number"] + 1, engine, mode, snapshot.get("player_actor_id"),
                    )
                    if mode == GeopoliticsMode.ACTOR_ROLE and snapshot["player_actor_id"]:
                        trigger = find_trigger_event(round_result, snapshot["player_actor_id"])
                        opts = build_actor_response_options(engine, snapshot["player_actor_id"], trigger or {})
                        new_dp_id = await create_geopolitics_decision_point(scenario_id, "geopolitics_actor_response", opts, next((o["id"] for o in opts if o.get("data", {}).get("engine_recommended")), opts[0]["id"]))
                    else:
                        opts = build_direction_options(round_result)
                        new_dp_id = await create_geopolitics_decision_point(scenario_id, "geopolitics_direction", opts, "maintain")
                    await link_snapshot_to_dp(snap_id, new_dp_id)
                    await conn.execute("UPDATE simulation_results SET status = 'simulating:geopolitics_paused' WHERE id = $1", row["id"])
                    return {"scenario_id": scenario_id, "result_id": row["id"], "status": "paused_again", "decision_point_id": new_dp_id}

            await conn.execute("UPDATE simulation_results SET status = 'completed' WHERE id = $1", row["id"])
            await conn.execute("UPDATE scenarios SET simulation_status = 'completed', status = 'completed' WHERE id = $1", scenario_id)
            return {"scenario_id": scenario_id, "result_id": row["id"], "status": "completed"}

        if status != "checkpoint:profiles" and not await mf_client.health_check():
            raise HTTPException(status_code=503, detail="MiroFish service unavailable")

        scn_row = await conn.fetchrow("SELECT max_rounds, simulation_params FROM scenarios WHERE id = $1", scenario_id)
        max_rounds = scn_row["max_rounds"] if scn_row else 10
        raw_params = scn_row["simulation_params"] if scn_row and "simulation_params" in scn_row else "{}"
        sim_params = SimulationParams.model_validate_json(raw_params or "{}")

    orchestrator = SimulationOrchestrator(mf_client, sb_client=sb_client)
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
