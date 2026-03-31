import json
import logging

import asyncpg
import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.clients.mirofish import MiroFishClient
from app.constants import DEFAULT_OFFSET, DEFAULT_PAGE_LIMIT
from app.database import get_db
from app.routers._helpers import get_mf_client, get_sim_row
from app.services.action_logger import ActionLogger

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scenario", tags=["simulation-live"])


@router.get("/{scenario_id}/live/stats")
async def get_live_stats(
    scenario_id: str,
    mf_client: MiroFishClient = Depends(get_mf_client),
    conn: asyncpg.Connection = Depends(get_db),
):
    """실시간 시뮬레이션 실행 상태 (run-status 프록시)."""
    row = await get_sim_row(conn, scenario_id)
    mf_sim_id = row["mirofish_simulation_id"]
    if not mf_sim_id:
        return {"status": row["status"], "message": "MiroFish simulation not yet created"}

    try:
        return await mf_client.get_run_status(mf_sim_id)
    except (httpx.HTTPError, RuntimeError, TimeoutError) as e:
        logger.warning("Failed to fetch live stats for scenario %s: %s", scenario_id, e)
        return {"status": row["status"], "message": "MiroFish unavailable"}


@router.get("/{scenario_id}/live/actions")
async def get_live_actions(
    scenario_id: str,
    offset: int = DEFAULT_OFFSET,
    limit: int = DEFAULT_PAGE_LIMIT,
    platform: str = "twitter",
    mf_client: MiroFishClient = Depends(get_mf_client),
    conn: asyncpg.Connection = Depends(get_db),
):
    """실시간 에이전트 액션 목록 (offset 기반 incremental)."""
    row = await get_sim_row(conn, scenario_id)
    mf_sim_id = row["mirofish_simulation_id"]
    if not mf_sim_id:
        return {"actions": [], "count": 0}

    try:
        return await mf_client.get_simulation_actions(
            mf_sim_id,
            platform=platform,
            limit=limit,
            offset=offset,
        )
    except (httpx.HTTPError, RuntimeError, TimeoutError) as e:
        logger.exception("Failed to fetch live actions for scenario %s", scenario_id)
        raise HTTPException(status_code=502, detail="Upstream service error") from e


@router.get("/{scenario_id}/live/graph_task")
async def get_live_graph_task(
    scenario_id: str,
    mf_client: MiroFishClient = Depends(get_mf_client),
    conn: asyncpg.Connection = Depends(get_db),
):
    """그래프 빌드 태스크 진행률."""
    row = await get_sim_row(conn, scenario_id)
    task_id = row["graph_task_id"]
    if not task_id:
        return {"status": row["status"], "message": "Graph build not started"}

    try:
        return await mf_client.get_task_status(task_id)
    except (httpx.HTTPError, RuntimeError, TimeoutError) as e:
        logger.exception("Failed to fetch live graph task for scenario %s", scenario_id)
        raise HTTPException(status_code=502, detail="Upstream service error") from e


@router.get("/{scenario_id}/live/graph_data")
async def get_live_graph_data(
    scenario_id: str,
    mf_client: MiroFishClient = Depends(get_mf_client),
    conn: asyncpg.Connection = Depends(get_db),
):
    """그래프 노드+엣지 데이터 (빌드 중에도 호출 가능)."""
    row = await get_sim_row(conn, scenario_id)
    graph_id = row["graph_id"]
    if not graph_id:
        return {"nodes": [], "edges": [], "node_count": 0, "edge_count": 0}

    try:
        return await mf_client.get_graph_data(graph_id)
    except (httpx.HTTPError, RuntimeError, TimeoutError) as e:
        logger.exception("Failed to fetch live graph data for scenario %s", scenario_id)
        raise HTTPException(status_code=502, detail="Upstream service error") from e


@router.get("/{scenario_id}/live/profiles")
async def get_live_profiles(
    scenario_id: str,
    platform: str = "twitter",
    mf_client: MiroFishClient = Depends(get_mf_client),
    conn: asyncpg.Connection = Depends(get_db),
):
    """프로필 생성 실시간 진행."""
    row = await get_sim_row(conn, scenario_id)
    mf_sim_id = row["mirofish_simulation_id"]
    if not mf_sim_id:
        return {"count": 0, "total_expected": 0, "is_generating": False, "profiles": []}

    try:
        return await mf_client.get_profiles_realtime(mf_sim_id, platform=platform)
    except (httpx.HTTPError, RuntimeError, TimeoutError) as e:
        logger.warning("Failed to fetch live profiles for scenario %s: %s", scenario_id, e)
        return {"count": 0, "total_expected": 0, "is_generating": False, "profiles": []}


@router.get("/{scenario_id}/live/config")
async def get_live_config(
    scenario_id: str,
    mf_client: MiroFishClient = Depends(get_mf_client),
    conn: asyncpg.Connection = Depends(get_db),
):
    """설정 생성 실시간 진행."""
    row = await get_sim_row(conn, scenario_id)
    mf_sim_id = row["mirofish_simulation_id"]
    if not mf_sim_id:
        return {"file_exists": False, "is_generating": False}

    try:
        return await mf_client.get_config_realtime(mf_sim_id)
    except (httpx.HTTPError, RuntimeError, TimeoutError) as e:
        logger.warning("Failed to fetch live config for scenario %s: %s", scenario_id, e)
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
    limit: int = DEFAULT_PAGE_LIMIT,
    offset: int = DEFAULT_OFFSET,
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
    limit: int = DEFAULT_PAGE_LIMIT,
    offset: int = DEFAULT_OFFSET,
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
    limit: int = DEFAULT_PAGE_LIMIT,
    offset: int = DEFAULT_OFFSET,
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
