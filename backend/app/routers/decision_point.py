import json
import logging
import uuid
from datetime import datetime, timezone

import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from app.database import get_db
from app.models.decision_point import (
    DecisionOption,
    DecisionPointCreate,
    DecisionPointResolveRequest,
    DecisionPointResponse,
)
from app.routers._helpers import row_to_decision_point
from app.services.action_logger import ActionLogger

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scenario", tags=["decision-points"])


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
    return row_to_decision_point(row)


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
        "decision_points": [row_to_decision_point(r) for r in rows],
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
    return row_to_decision_point(row)


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
    return row_to_decision_point(updated)
