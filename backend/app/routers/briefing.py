import json
import logging
from datetime import datetime, timezone

import asyncpg
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse, Response

from app.clients.shadowbroker import ShadowBrokerClient
from app.database import get_db
from app.routers._helpers import get_sb_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scenario", tags=["briefing"])


@router.post("/{scenario_id}/briefing/generate", status_code=201)
async def generate_briefing(
    scenario_id: str,
    sb_client: ShadowBrokerClient = Depends(get_sb_client),
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

    generator = BriefingGenerator(sb_client=sb_client)
    try:
        briefing = await generator.generate(scenario_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (httpx.HTTPError, ValueError) as e:
        logger.exception("Briefing generation failed for scenario %s", scenario_id)
        raise HTTPException(status_code=500, detail="Briefing generation failed") from e

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
