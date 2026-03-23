import json
import uuid
from datetime import datetime, timezone

import asyncpg
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.database import get_db
from app.models.scenario import (
    ScenarioCreate,
    ScenarioCreatedResponse,
    ScenarioResponse,
    SimulationParams,
)
from app.services.action_logger import ActionLogger

router = APIRouter(prefix="/api/scenario", tags=["scenario"])


@router.post("", response_model=ScenarioCreatedResponse, status_code=201)
async def create_scenario(
    data: ScenarioCreate, conn: asyncpg.Connection = Depends(get_db)
):
    scenario_id = f"scn_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()

    await conn.execute(
        """INSERT INTO scenarios
           (id, name, region_bbox, region_name, question, max_rounds, data_sources,
            simulation_params, status, seed_status, simulation_status, created_at, updated_at)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'created', 'pending', 'pending', $9, $10)""",
        scenario_id,
        data.name,
        json.dumps(data.region.bbox),
        data.region.name,
        data.question,
        data.max_rounds,
        json.dumps(data.data_sources),
        data.simulation_params.model_dump_json(),
        now,
        now,
    )
    await ActionLogger.log(
        "scenario.create",
        scenario_id,
        payload={"name": data.name, "region": data.region.name},
    )

    return ScenarioCreatedResponse(
        id=scenario_id,
        status="created",
        seed_status="pending",
        simulation_status="pending",
    )


@router.get("")
async def list_scenarios(
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    region: Optional[str] = Query(None),
    created_after: Optional[str] = Query(None),
    created_before: Optional[str] = Query(None),
    sort: str = Query("created_at"),
    order: str = Query("desc"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    conn: asyncpg.Connection = Depends(get_db),
):
    conditions: list[str] = []
    params: list = []
    idx = 1

    if q:
        conditions.append(f"(name ILIKE ${idx} OR question ILIKE ${idx} OR region_name ILIKE ${idx})")
        params.append(f"%{q}%")
        idx += 1

    if status:
        conditions.append(f"status = ${idx}")
        params.append(status)
        idx += 1

    if region:
        conditions.append(f"region_name ILIKE ${idx}")
        params.append(f"%{region}%")
        idx += 1

    if created_after:
        conditions.append(f"created_at >= ${idx}")
        params.append(created_after)
        idx += 1

    if created_before:
        conditions.append(f"created_at <= ${idx}")
        params.append(created_before)
        idx += 1

    where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
    sort_col = sort if sort in ("created_at", "updated_at", "name", "status") else "created_at"
    sort_dir = "ASC" if order.lower() == "asc" else "DESC"

    count_row = await conn.fetchrow(f"SELECT COUNT(*) as total FROM scenarios{where}", *params)
    total = count_row["total"] if count_row else 0

    rows = await conn.fetch(
        f"SELECT * FROM scenarios{where} ORDER BY {sort_col} {sort_dir} LIMIT ${idx} OFFSET ${idx + 1}",
        *params, limit, offset,
    )

    return {"scenarios": [_row_to_response(row) for row in rows], "total": total}


@router.get("/{scenario_id}", response_model=ScenarioResponse)
async def get_scenario(
    scenario_id: str, conn: asyncpg.Connection = Depends(get_db)
):
    row = await conn.fetchrow("SELECT * FROM scenarios WHERE id = $1", scenario_id)
    if not row:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return _row_to_response(row)


@router.delete("/{scenario_id}", status_code=204)
async def delete_scenario(
    scenario_id: str, conn: asyncpg.Connection = Depends(get_db)
):
    result = await conn.execute("DELETE FROM scenarios WHERE id = $1", scenario_id)
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Scenario not found")
    await ActionLogger.log("scenario.delete", scenario_id)


@router.get("/{scenario_id_a}/compare/{scenario_id_b}")
async def compare_scenarios(
    scenario_id_a: str,
    scenario_id_b: str,
    conn: asyncpg.Connection = Depends(get_db),
):
    from app.services.scenario_comparator import ScenarioComparator

    try:
        result = await ScenarioComparator().compare(scenario_id_a, scenario_id_b)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return result


def _row_to_response(row: asyncpg.Record) -> ScenarioResponse:
    raw_params = row["simulation_params"] if "simulation_params" in row else "{}"
    sim_params = SimulationParams.model_validate_json(raw_params or "{}")

    return ScenarioResponse(
        id=row["id"],
        name=row["name"],
        region_bbox=json.loads(row["region_bbox"]),
        region_name=row["region_name"],
        question=row["question"],
        max_rounds=row["max_rounds"],
        data_sources=json.loads(row["data_sources"]),
        simulation_params=sim_params,
        status=row["status"],
        seed_status=row["seed_status"],
        simulation_status=row["simulation_status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
