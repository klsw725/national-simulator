import json
import logging
import uuid
from datetime import datetime, timezone

import asyncpg
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from app.database import get_db
from app.models.result import (
    CheckpointResponse,
    ContinueRequest,
    SimulateRequest,
    SimulationResultResponse,
)
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
    await ActionLogger.log(
        "seed.generate",
        scenario_id,
        payload={
            "seed_id": seed_id,
            "vessels_count": result["metadata"].get("vessels_count", 0),
        },
    )

    return SeedResponse(
        id=seed_id,
        scenario_id=scenario_id,
        text=result["text"],
        metadata=SeedMetadata(**result["metadata"]),
        created_at=now,
    )


@router.get("/{scenario_id}/seed", response_model=SeedResponse)
async def get_seed(
    scenario_id: str,
    conn: asyncpg.Connection = Depends(get_db),
):
    """생성된 시드 문서를 조회한다."""
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
}


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
    if mode not in ("auto", "checkpoint"):
        raise HTTPException(status_code=400, detail="mode must be 'auto' or 'checkpoint'")

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

    if mode == "checkpoint":
        await conn.execute(
            """INSERT INTO simulation_results
               (id, scenario_id, status, platform, pipeline_mode, created_at)
               VALUES ($1, $2, 'checkpoint:seed', 'twitter', 'checkpoint', $3)""",
            result_id,
            scenario_id,
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

    mf_client = request.app.state.mf_client
    if not await mf_client.health_check():
        raise HTTPException(status_code=503, detail="MiroFish service unavailable")

    await conn.execute(
        """INSERT INTO simulation_results
           (id, scenario_id, status, platform, pipeline_mode, created_at)
           VALUES ($1, $2, 'starting', 'twitter', 'auto', $3)""",
        result_id,
        scenario_id,
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
    )
    await ActionLogger.log(
        "simulation.start",
        scenario_id,
        payload={
            "result_id": result_id,
            "mode": "auto",
            "max_rounds": scenario["max_rounds"],
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

    return CheckpointResponse(
        scenario_id=scenario_id,
        result_id=row["id"],
        status=status,
        step=step_info["step"],
        editable=step_info["editable"],
        data=checkpoint_data,
    )


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

    if row["pipeline_mode"] != "checkpoint":
        raise HTTPException(status_code=400, detail="Pipeline is not in checkpoint mode")

    mf_client = request.app.state.mf_client
    if status != "checkpoint:profiles" and not await mf_client.health_check():
        raise HTTPException(status_code=503, detail="MiroFish service unavailable")

    scn_row = await conn.fetchrow("SELECT max_rounds FROM scenarios WHERE id = $1", scenario_id)
    max_rounds = scn_row["max_rounds"] if scn_row else 10

    orchestrator = SimulationOrchestrator(mf_client, sb_client=request.app.state.sb_client)
    edits = body.edits if body else None

    background_tasks.add_task(
        orchestrator.run_from_checkpoint,
        scenario_id=scenario_id,
        result_id=row["id"],
        max_rounds=max_rounds,
        edits=edits,
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

    return {
        "scenario_id": scenario_id,
        "result_id": row["id"],
        "status": row["status"],
        "mirofish_project_id": row["mirofish_project_id"],
        "mirofish_simulation_id": row["mirofish_simulation_id"],
        "created_at": row["created_at"],
        "completed_at": row["completed_at"],
    }


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
    except Exception:
        return {"actions": [], "count": 0}


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
    except Exception:
        return {"status": "unknown", "progress": 0}


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
    except Exception:
        return {"nodes": [], "edges": [], "node_count": 0, "edge_count": 0}


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
