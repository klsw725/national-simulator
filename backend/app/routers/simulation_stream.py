from __future__ import annotations

import asyncio
import json
import logging

import asyncpg
from fastapi import APIRouter, Request
from starlette.responses import StreamingResponse

from app.config import settings
from app.services.pg_event_bus import (
    CHANNEL_SIM_EVENTS,
    catch_up_events,
    resolve_event_ref,
)

logger = logging.getLogger(__name__)
router = APIRouter()

_HEARTBEAT_INTERVAL = 30


@router.get("/api/scenario/{scenario_id}/stream")
async def scenario_event_stream(
    scenario_id: str, request: Request, last_event_id: int | None = None,
):
    async def _generate():
        conn = await asyncpg.connect(settings.database_url)
        queue: asyncio.Queue[str] = asyncio.Queue()
        listener_registered = False

        def _on_notification(
            _conn: asyncpg.Connection,
            _pid: int,
            _channel: str,
            payload: str,
        ) -> None:
            queue.put_nowait(payload)

        try:
            await conn.add_listener(CHANNEL_SIM_EVENTS, _on_notification)
            listener_registered = True

            catch_up_after = request.headers.get("Last-Event-ID")
            if catch_up_after is None and last_event_id is not None:
                catch_up_after = str(last_event_id)
            if catch_up_after is not None:
                try:
                    missed = await catch_up_events(scenario_id, int(catch_up_after))
                    for evt in missed:
                        seq = evt.get("sequence_num", "")
                        evt_type = evt.get("type", "message")
                        data = json.dumps(evt, ensure_ascii=False)
                        yield f"event: {evt_type}\nid: {seq}\ndata: {data}\n\n"
                except (ValueError, Exception):
                    logger.warning("Failed catch-up for last_event_id=%s", catch_up_after)

            while True:
                try:
                    raw = await asyncio.wait_for(queue.get(), timeout=_HEARTBEAT_INTERVAL)
                except asyncio.TimeoutError:
                    if await request.is_disconnected():
                        break
                    yield ": keepalive\n\n"
                    continue

                if await request.is_disconnected():
                    break

                try:
                    event = json.loads(raw)
                    event = await resolve_event_ref(event)
                except (json.JSONDecodeError, Exception):
                    logger.warning("Invalid event payload: %s", raw[:200])
                    continue

                if event.get("scenario_id") != scenario_id:
                    continue

                evt_type = event.get("type", "message")
                seq = event.get("sequence_num", "")
                data = json.dumps(event, ensure_ascii=False)
                yield f"event: {evt_type}\nid: {seq}\ndata: {data}\n\n"

        finally:
            if listener_registered and not conn.is_closed():
                await conn.remove_listener(CHANNEL_SIM_EVENTS, _on_notification)
            if not conn.is_closed():
                await conn.close()

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
