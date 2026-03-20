import json
import logging
import uuid
from datetime import datetime, timezone

import aiosqlite
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import get_db
from app.models.result import (
    CheckpointResponse,
    ContinueRequest,
    SimulateRequest,
    SimulationResultResponse,
)
from app.models.seed import SeedMetadata, SeedResponse
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
    db: aiosqlite.Connection = Depends(get_db),
):
    """시드 문서를 생성하고 저장한다."""
    # 1. 시나리오 조회
    cursor = await db.execute(
        "SELECT * FROM scenarios WHERE id = ?", (scenario_id,)
    )
    scenario = await cursor.fetchone()
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    # 이미 생성된 시드가 있으면 반환
    cursor = await db.execute(
        "SELECT * FROM seeds WHERE scenario_id = ?", (scenario_id,)
    )
    existing = await cursor.fetchone()
    if existing:
        return _row_to_seed_response(existing)

    # 2. 시드 생성
    sb_client = request.app.state.sb_client
    generator = SeedGenerator(sb_client)

    bbox = json.loads(scenario["region_bbox"])
    question = scenario["question"]
    region_name = scenario["region_name"]

    try:
        await db.execute(
            "UPDATE scenarios SET seed_status = 'generating', updated_at = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), scenario_id),
        )
        await db.commit()

        result = await generator.generate(
            bbox=bbox,
            question=question,
            region_name=region_name,
        )
    except Exception:
        logger.exception("Seed generation failed for scenario %s", scenario_id)
        await db.execute(
            "UPDATE scenarios SET seed_status = 'failed', updated_at = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), scenario_id),
        )
        await db.commit()
        raise HTTPException(status_code=500, detail="Seed generation failed")

    # 3. DB 저장
    seed_id = f"seed_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()

    await db.execute(
        "INSERT INTO seeds (id, scenario_id, text, metadata, created_at) VALUES (?, ?, ?, ?, ?)",
        (
            seed_id,
            scenario_id,
            result["text"],
            json.dumps(result["metadata"], ensure_ascii=False),
            now,
        ),
    )
    await db.execute(
        "UPDATE scenarios SET seed_status = 'completed', updated_at = ? WHERE id = ?",
        (now, scenario_id),
    )
    await db.commit()

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
    db: aiosqlite.Connection = Depends(get_db),
):
    """생성된 시드 문서를 조회한다."""
    cursor = await db.execute(
        "SELECT * FROM seeds WHERE scenario_id = ?", (scenario_id,)
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Seed not found for this scenario")
    return _row_to_seed_response(row)


def _row_to_seed_response(row: aiosqlite.Row) -> SeedResponse:
    return SeedResponse(
        id=row["id"],
        scenario_id=row["scenario_id"],
        text=row["text"],
        metadata=SeedMetadata(**json.loads(row["metadata"])),
        created_at=row["created_at"],
    )


# ------------------------------------------------------------------
# Simulation endpoints (PRD 4)
# ------------------------------------------------------------------


@router.post("/{scenario_id}/simulate", status_code=202)
async def start_simulation(
    scenario_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    body: SimulateRequest | None = None,
    db: aiosqlite.Connection = Depends(get_db),
):
    """시뮬레이션 파이프라인을 시작한다.

    mode="auto": 기존 동작 (전부 자동, 백그라운드 실행)
    mode="checkpoint": 첫 체크포인트(시드 검토)에서 일시정지
    """
    mode = (body.mode if body else "auto") or "auto"
    if mode not in ("auto", "checkpoint"):
        raise HTTPException(status_code=400, detail="mode must be 'auto' or 'checkpoint'")

    cursor = await db.execute(
        "SELECT * FROM scenarios WHERE id = ?", (scenario_id,)
    )
    scenario = await cursor.fetchone()
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    if scenario["seed_status"] != "completed":
        raise HTTPException(
            status_code=400,
            detail="Seed must be generated first (POST /api/scenario/{id}/seed)",
        )

    # 이미 실행 중인지 확인
    cursor = await db.execute(
        "SELECT * FROM simulation_results WHERE scenario_id = ? AND status NOT IN ('completed', 'failed')",
        (scenario_id,),
    )
    running = await cursor.fetchone()
    if running:
        raise HTTPException(status_code=409, detail="Simulation already in progress")

    # 시드 텍스트 조회
    cursor = await db.execute(
        "SELECT text FROM seeds WHERE scenario_id = ?", (scenario_id,)
    )
    seed_row = await cursor.fetchone()
    if not seed_row:
        raise HTTPException(status_code=400, detail="Seed document not found")

    result_id = f"simr_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()

    if mode == "checkpoint":
        # checkpoint 모드: 시드 검토 단계에서 즉시 일시정지
        await db.execute(
            """INSERT INTO simulation_results
               (id, scenario_id, status, platform, pipeline_mode, created_at)
               VALUES (?, ?, 'checkpoint:seed', 'twitter', 'checkpoint', ?)""",
            (result_id, scenario_id, now),
        )
        await db.execute(
            "UPDATE scenarios SET simulation_status = 'checkpoint', status = 'checkpoint', updated_at = ? WHERE id = ?",
            (now, scenario_id),
        )
        await db.commit()

        return {
            "scenario_id": scenario_id,
            "result_id": result_id,
            "status": "checkpoint:seed",
            "pipeline_mode": "checkpoint",
            "message": "Pipeline paused at seed review checkpoint",
        }

    # auto 모드: 기존 동작
    mf_client = request.app.state.mf_client
    if not await mf_client.health_check():
        raise HTTPException(status_code=503, detail="MiroFish service unavailable")

    await db.execute(
        """INSERT INTO simulation_results
           (id, scenario_id, status, platform, pipeline_mode, created_at)
           VALUES (?, ?, 'starting', 'twitter', 'auto', ?)""",
        (result_id, scenario_id, now),
    )
    await db.execute(
        "UPDATE scenarios SET simulation_status = 'simulating', status = 'simulating', updated_at = ? WHERE id = ?",
        (now, scenario_id),
    )
    await db.commit()

    orchestrator = SimulationOrchestrator(mf_client)
    background_tasks.add_task(
        orchestrator.run_pipeline,
        scenario_id=scenario_id,
        result_id=result_id,
        seed_text=seed_row["text"],
        max_rounds=scenario["max_rounds"],
        db_path=settings.database_path,
    )

    return {
        "scenario_id": scenario_id,
        "result_id": result_id,
        "status": "starting",
        "pipeline_mode": "auto",
        "message": "Simulation pipeline started in background",
    }


CHECKPOINT_STEPS = {
    "checkpoint:seed": {"step": "seed", "editable": True},
    "checkpoint:ontology": {"step": "ontology", "editable": False},
    "checkpoint:graph": {"step": "graph", "editable": False},
    "checkpoint:profiles": {"step": "profiles", "editable": False},
    "checkpoint:config": {"step": "config", "editable": True},
}


@router.get("/{scenario_id}/checkpoint", response_model=CheckpointResponse)
async def get_checkpoint(
    scenario_id: str,
    db: aiosqlite.Connection = Depends(get_db),
):
    cursor = await db.execute(
        "SELECT * FROM simulation_results WHERE scenario_id = ? ORDER BY created_at DESC LIMIT 1",
        (scenario_id,),
    )
    row = await cursor.fetchone()
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
        seed_cursor = await db.execute(
            "SELECT text FROM seeds WHERE scenario_id = ? ORDER BY created_at DESC LIMIT 1",
            (scenario_id,),
        )
        seed_row = await seed_cursor.fetchone()
        checkpoint_data = {"seed_text": seed_row["text"]} if seed_row else None

    if status == "checkpoint:config":
        scn_cursor = await db.execute(
            "SELECT max_rounds FROM scenarios WHERE id = ?", (scenario_id,)
        )
        scn_row = await scn_cursor.fetchone()
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
    db: aiosqlite.Connection = Depends(get_db),
):
    cursor = await db.execute(
        "SELECT * FROM simulation_results WHERE scenario_id = ? ORDER BY created_at DESC LIMIT 1",
        (scenario_id,),
    )
    row = await cursor.fetchone()
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

    scn_cursor = await db.execute(
        "SELECT max_rounds FROM scenarios WHERE id = ?", (scenario_id,)
    )
    scn_row = await scn_cursor.fetchone()
    max_rounds = scn_row["max_rounds"] if scn_row else 10

    orchestrator = SimulationOrchestrator(mf_client)
    edits = body.edits if body else None

    background_tasks.add_task(
        orchestrator.run_from_checkpoint,
        scenario_id=scenario_id,
        result_id=row["id"],
        db_path=settings.database_path,
        max_rounds=max_rounds,
        edits=edits,
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
    db: aiosqlite.Connection = Depends(get_db),
):
    """시뮬레이션 파이프라인 현재 상태를 조회한다."""
    cursor = await db.execute(
        "SELECT * FROM simulation_results WHERE scenario_id = ? ORDER BY created_at DESC LIMIT 1",
        (scenario_id,),
    )
    row = await cursor.fetchone()
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
    db: aiosqlite.Connection = Depends(get_db),
):
    """시뮬레이션 결과를 조회한다."""
    cursor = await db.execute(
        "SELECT * FROM simulation_results WHERE scenario_id = ? ORDER BY created_at DESC LIMIT 1",
        (scenario_id,),
    )
    row = await cursor.fetchone()
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


# ------------------------------------------------------------------
# Result Projection endpoints (PRD 5)
# ------------------------------------------------------------------


@router.get("/{scenario_id}/geojson")
async def get_geojson(
    scenario_id: str,
    db: aiosqlite.Connection = Depends(get_db),
):
    """시뮬레이션 결과를 GeoJSON FeatureCollection으로 반환한다."""
    from app.services.result_projector import ResultProjector

    cursor = await db.execute(
        "SELECT * FROM simulation_results WHERE scenario_id = ? ORDER BY created_at DESC LIMIT 1",
        (scenario_id,),
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="No simulation found for this scenario")

    if row["status"] != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Simulation not completed yet (status: {row['status']})",
        )

    # 캐시된 geojson이 있으면 반환
    if row["geojson"]:
        return json.loads(row["geojson"])

    # 없으면 생성 후 캐시
    results = json.loads(row["results"]) if row["results"] else {}

    # 시나리오 bbox에서 fallback 중심점 계산
    cursor2 = await db.execute(
        "SELECT region_bbox FROM scenarios WHERE id = ?", (scenario_id,)
    )
    scn = await cursor2.fetchone()
    fallback = None
    if scn:
        bbox = json.loads(scn["region_bbox"])
        fallback = ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)

    projector = ResultProjector()
    geojson = projector.project_to_geojson(results, fallback_center=fallback)

    # DB에 캐시
    await db.execute(
        "UPDATE simulation_results SET geojson = ? WHERE id = ?",
        (json.dumps(geojson, ensure_ascii=False), row["id"]),
    )
    await db.commit()

    return geojson


@router.get("/{scenario_id}/report")
async def get_report(
    scenario_id: str,
    db: aiosqlite.Connection = Depends(get_db),
):
    """MiroFish 시뮬레이션 보고서를 반환한다."""
    cursor = await db.execute(
        "SELECT * FROM simulation_results WHERE scenario_id = ? ORDER BY created_at DESC LIMIT 1",
        (scenario_id,),
    )
    row = await cursor.fetchone()
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
