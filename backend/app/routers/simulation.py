import json
import logging
import uuid
from datetime import datetime, timezone

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from app.database import get_db
from app.models.seed import SeedMetadata, SeedResponse
from app.services.seed_generator import SeedGenerator

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


# --- PRD 4, 5 스텁 (미구현) ---


@router.post("/{scenario_id}/simulate")
async def start_simulation(scenario_id: str):
    return _not_impl("PRD 4 (simulation-orchestration)")


@router.get("/{scenario_id}/status")
async def get_simulation_status(scenario_id: str):
    return _not_impl("PRD 4 (simulation-orchestration)")


@router.get("/{scenario_id}/results")
async def get_simulation_results(scenario_id: str):
    return _not_impl("PRD 4 (simulation-orchestration)")


@router.get("/{scenario_id}/geojson")
async def get_geojson(scenario_id: str):
    return _not_impl("PRD 5 (result-projection)")


@router.get("/{scenario_id}/report")
async def get_report(scenario_id: str):
    return _not_impl("PRD 5 (result-projection)")
