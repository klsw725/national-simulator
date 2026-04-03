from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Coroutine

import asyncpg

from app.config import settings
from app.database import get_pool

logger = logging.getLogger(__name__)

_NOTIFY_PAYLOAD_LIMIT = 7000

CHANNEL_SIM_EVENTS = "sim_events"
CHANNEL_SIM_COMMANDS = "sim_commands"


async def emit_event(channel: str, event: dict[str, Any]) -> int | None:
    """NOTIFY로 이벤트 발행. 8KB 초과 시 DB에 저장 후 참조 ID 전송.

    Returns:
        sequence_num if stored in DB, None if sent inline.
    """
    payload = json.dumps(event, ensure_ascii=False)
    pool = get_pool()

    if len(payload.encode("utf-8")) > _NOTIFY_PAYLOAD_LIMIT:
        seq = await _store_and_notify(pool, channel, event)
        return seq

    async with pool.acquire() as conn:
        await conn.execute(f"SELECT pg_notify($1, $2)", channel, payload)
    return None


async def _store_and_notify(
    pool: asyncpg.Pool,
    channel: str,
    event: dict[str, Any],
) -> int:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO simulation_events (scenario_id, event_type, payload)
               VALUES ($1, $2, $3)
               RETURNING sequence_num""",
            event.get("scenario_id", ""),
            event.get("type", "unknown"),
            json.dumps(event, ensure_ascii=False),
        )
        seq = row["sequence_num"]
        ref_payload = json.dumps(
            {"type": "event_ref", "event_id": str(seq)},
            ensure_ascii=False,
        )
        await conn.execute(f"SELECT pg_notify($1, $2)", channel, ref_payload)
    return seq


async def catch_up_events(
    scenario_id: str,
    after_sequence: int,
) -> list[dict[str, Any]]:
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT sequence_num, event_type, payload
               FROM simulation_events
               WHERE scenario_id = $1 AND sequence_num > $2
               ORDER BY sequence_num""",
            scenario_id,
            after_sequence,
        )
    return [
        {
            "sequence_num": row["sequence_num"],
            "type": row["event_type"],
            **json.loads(row["payload"]),
        }
        for row in rows
    ]


async def resolve_event_ref(event: dict[str, Any]) -> dict[str, Any]:
    if event.get("type") != "event_ref":
        return event
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT payload FROM simulation_events WHERE sequence_num = $1",
            int(event["event_id"]),
        )
    if not row:
        logger.warning("event_ref %s not found in DB", event["event_id"])
        return event
    return json.loads(row["payload"])


ListenerCallback = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]


async def listen_events(
    channel: str,
    callback: ListenerCallback,
    *,
    reconnect_base_delay: float = 1.0,
    reconnect_max_delay: float = 30.0,
) -> None:
    delay = reconnect_base_delay
    while True:
        try:
            conn = await asyncpg.connect(settings.database_url)
            delay = reconnect_base_delay
            queue: asyncio.Queue[str] = asyncio.Queue()

            def _on_notification(
                _conn: asyncpg.Connection,
                _pid: int,
                _channel: str,
                payload: str,
            ) -> None:
                queue.put_nowait(payload)

            await conn.add_listener(channel, _on_notification)
            logger.info("LISTEN %s started", channel)

            try:
                while True:
                    raw = await queue.get()
                    try:
                        event = json.loads(raw)
                        event = await resolve_event_ref(event)
                        await callback(event)
                    except json.JSONDecodeError:
                        logger.warning("Invalid JSON on %s: %s", channel, raw[:200])
                    except Exception:
                        logger.exception("Callback error on %s", channel)
            finally:
                await conn.remove_listener(channel, _on_notification)
                await conn.close()

        except asyncio.CancelledError:
            logger.info("LISTEN %s cancelled", channel)
            raise
        except Exception:
            logger.exception("LISTEN %s connection lost, reconnecting in %.1fs", channel, delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, reconnect_max_delay)
