import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.database import get_pool
from app.services.event_bus import event_bus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scenario", tags=["simulation-events"])


async def _build_catchup_event(scenario_id: str) -> dict | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        dp = await conn.fetchrow(
            "SELECT * FROM decision_points "
            "WHERE scenario_id = $1 AND status = 'pending' "
            "ORDER BY created_at DESC LIMIT 1",
            scenario_id,
        )
        if not dp:
            return None

        briefing_row = await conn.fetchrow(
            """SELECT payload FROM action_log
               WHERE scenario_id = $1 AND action_type = 'wargame.round_briefing'
               ORDER BY created_at DESC LIMIT 1""",
            scenario_id,
        )
        briefing = None
        if briefing_row and briefing_row["payload"]:
            try:
                payload = json.loads(briefing_row["payload"])
                if payload.get("decision_point_id") == dp["id"]:
                    briefing = payload.get("briefing")
            except (json.JSONDecodeError, TypeError):
                pass

        options = json.loads(dp["options"]) if dp["options"] else []
        return {
            "type": "decision_required",
            "data": {
                "round": briefing.get("round") if briefing else 0,
                "decision_point_id": dp["id"],
                "briefing": briefing,
                "decision_point": {
                    "id": dp["id"],
                    "scenario_id": dp["scenario_id"],
                    "type": dp["type"],
                    "options": options,
                    "recommended": dp["recommended"],
                    "allow_custom": dp["allow_custom"],
                    "status": dp["status"],
                    "selected_option_id": dp["selected_option_id"],
                    "custom_data": dp["custom_data"],
                    "created_at": dp["created_at"].isoformat() if dp["created_at"] else None,
                    "resolved_at": dp["resolved_at"].isoformat() if dp["resolved_at"] else None,
                },
            },
        }


@router.get("/{scenario_id}/events")
async def simulation_events(scenario_id: str):
    async def event_generator():
        try:
            catchup = await _build_catchup_event(scenario_id)
        except Exception:
            logger.debug("SSE catch-up failed for %s, skipping", scenario_id)
            catchup = None

        if catchup:
            data = json.dumps(catchup.get("data", {}), ensure_ascii=False)
            yield f"event: {catchup['type']}\ndata: {data}\n\n"

        async for event in event_bus.subscribe(scenario_id):
            data = json.dumps(event.get("data", {}), ensure_ascii=False)
            yield f"event: {event['type']}\ndata: {data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
