import json

import asyncpg
from fastapi import APIRouter, Depends

from app.database import get_db

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
async def get_dashboard(conn: asyncpg.Connection = Depends(get_db)):
    total = await conn.fetchval("SELECT COUNT(*) FROM scenarios")

    status_rows = await conn.fetch(
        "SELECT status, COUNT(*) as cnt FROM scenarios GROUP BY status"
    )
    by_status = {r["status"]: r["cnt"] for r in status_rows}

    region_rows = await conn.fetch(
        "SELECT region_name, COUNT(*) as cnt FROM scenarios GROUP BY region_name ORDER BY cnt DESC LIMIT 10"
    )
    by_region = {r["region_name"]: r["cnt"] for r in region_rows}

    recent_rows = await conn.fetch(
        "SELECT scenario_id, action_type, actor, created_at FROM action_log ORDER BY created_at DESC LIMIT 10"
    )
    recent_activity = [
        {
            "scenario_id": r["scenario_id"],
            "action": r["action_type"],
            "actor": r["actor"],
            "timestamp": r["created_at"],
        }
        for r in recent_rows
    ]

    running_rows = await conn.fetch(
        "SELECT s.id, s.name, sr.status FROM scenarios s LEFT JOIN simulation_results sr ON sr.scenario_id = s.id WHERE s.status NOT IN ('completed', 'failed', 'created') ORDER BY s.updated_at DESC LIMIT 5"
    )
    running = [
        {"id": r["id"], "name": r["name"], "status": r["status"] or "unknown"}
        for r in running_rows
    ]

    return {
        "total_scenarios": total,
        "by_status": by_status,
        "by_region": by_region,
        "recent_activity": recent_activity,
        "running_simulations": running,
    }
