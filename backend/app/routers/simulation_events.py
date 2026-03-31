import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.services.event_bus import event_bus

router = APIRouter(prefix="/api/scenario", tags=["simulation-events"])


@router.get("/{scenario_id}/events")
async def simulation_events(scenario_id: str):
    async def event_generator():
        async for event in event_bus.subscribe(scenario_id):
            data = json.dumps(event.get("data", {}), ensure_ascii=False)
            yield f"event: {event['type']}\ndata: {data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
