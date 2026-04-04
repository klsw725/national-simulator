from __future__ import annotations

import asyncio
import json
import logging

import asyncpg
import httpx

from app.config import settings

logger = logging.getLogger(__name__)

POLL_INTERVAL = 300
GDELT_CLASSIFY_MAP = {
    "01": "diplomatic",
    "02": "diplomatic",
    "03": "diplomatic",
    "04": "diplomatic",
    "05": "diplomatic",
    "06": "diplomatic",
    "07": "diplomatic",
    "08": "diplomatic",
    "09": "diplomatic",
    "10": "diplomatic",
    "11": "diplomatic",
    "12": "economic",
    "13": "economic",
    "14": "military",
    "15": "military",
    "17": "military",
    "18": "military",
    "19": "military",
    "20": "military",
}


def classify_gdelt_event(event_code: str) -> str:
    prefix = event_code[:2] if event_code else ""
    return GDELT_CLASSIFY_MAP.get(prefix, "diplomatic")


async def gdelt_poll_loop() -> None:
    try:
        pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=2)
    except Exception:
        logger.exception("GDELT pipeline: DB pool creation failed")
        return

    while True:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(f"{settings.shadowbroker_url}/api/live-data/slow")
                resp.raise_for_status()
                data = resp.json()

            gdelt_events = data.get("gdelt", [])
            if not gdelt_events:
                await asyncio.sleep(POLL_INTERVAL)
                continue

            async with pool.acquire() as conn:
                for evt in gdelt_events[:50]:
                    event_code = str(evt.get("event_code", evt.get("EventCode", "")))
                    category = classify_gdelt_event(event_code)
                    goldstein = evt.get("goldstein_scale", evt.get("GoldsteinScale", 0))

                    await conn.execute(
                        """INSERT INTO geopolitics_events
                           (id, scenario_id, action_type, actor_id, target_actor_ids,
                            content, magnitude, event_at)
                           VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
                           ON CONFLICT DO NOTHING""",
                        f"gdelt_{evt.get('GlobalEventID', evt.get('id', ''))}",
                        "",
                        category,
                        evt.get("Actor1CountryCode", ""),
                        evt.get("Actor2CountryCode", ""),
                        json.dumps(evt, ensure_ascii=False)[:4000],
                        abs(goldstein) / 10.0 if goldstein else 0.5,
                    )

            logger.info("GDELT pipeline: stored %d events", min(len(gdelt_events), 50))

        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("GDELT pipeline poll failed")

        await asyncio.sleep(POLL_INTERVAL)
