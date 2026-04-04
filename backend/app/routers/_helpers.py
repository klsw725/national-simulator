"""Shared helpers for scenario sub-routers."""
import json

import asyncpg
from fastapi import HTTPException, Request

from app.clients.shadowbroker import ShadowBrokerClient
from app.models.decision_point import DecisionOption, DecisionPointResponse
from app.models.seed import SeedMetadata, SeedResponse


async def get_sim_row(conn: asyncpg.Connection, scenario_id: str) -> asyncpg.Record:
    """시나리오의 최신 simulation_results 행을 반환. 없으면 404."""
    row = await conn.fetchrow(
        "SELECT * FROM simulation_results WHERE scenario_id = $1 ORDER BY created_at DESC LIMIT 1",
        scenario_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="No simulation found for this scenario")
    return row


def row_to_seed_response(row: asyncpg.Record) -> SeedResponse:
    return SeedResponse(
        id=row["id"],
        scenario_id=row["scenario_id"],
        text=row["text"],
        metadata=SeedMetadata(**json.loads(row["metadata"])),
        created_at=row["created_at"],
    )


def row_to_decision_point(row: asyncpg.Record) -> DecisionPointResponse:
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


def get_sb_client(request: Request) -> ShadowBrokerClient:
    return request.app.state.sb_client
