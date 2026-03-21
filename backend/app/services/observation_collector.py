from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from app.clients.shadowbroker import BBox, ShadowBrokerClient
from app.database import get_pool
from app.resolution.resolver import Resolver

# AGENTS.md 지뢰: Ships/flights/satellites는 lng, CCTV/KiwiSDR은 lon
_LNG_FIELD = {"ship": "lng", "flight": "lng", "satellite": "lng"}


class ObservationCollector:
    def __init__(self, sb_client: ShadowBrokerClient) -> None:
        self._sb = sb_client
        self._resolver = Resolver()

    async def collect(
        self,
        source_type: str = "ship",
        bbox: BBox | None = None,
        auto_resolve: bool = True,
    ) -> dict[str, Any]:
        raw_items = await self._fetch_from_sb(source_type, bbox)
        if not raw_items:
            return {"source_type": source_type, "collected": 0, "resolved": 0}

        inserted = await self._insert_observations(source_type, raw_items)

        resolved_count = 0
        if auto_resolve:
            for obs in inserted:
                result = await self._resolver.auto_resolve(
                    observation_id=obs["id"],
                    source_type=obs["source_type"],
                    source_id=obs["source_id"],
                    raw_data=obs["raw_data"],
                )
                resolved_count += len(result.get("auto_resolved", []))

        return {
            "source_type": source_type,
            "collected": len(inserted),
            "resolved": resolved_count,
        }

    async def _fetch_from_sb(self, source_type: str, bbox: BBox | None) -> list[dict]:
        data = await self._sb.get_fast_data(bbox)

        source_key_map = {
            "ship": "ships",
            "flight": "flights",
            "satellite": "satellites",
        }
        key = source_key_map.get(source_type, source_type)
        items = data.get(key, [])
        return items if isinstance(items, list) else []

    async def _insert_observations(
        self, source_type: str, items: list[dict],
    ) -> list[dict[str, Any]]:
        pool = get_pool()
        now = datetime.now(timezone.utc).isoformat()
        lng_field = _LNG_FIELD.get(source_type, "lng")
        inserted: list[dict[str, Any]] = []

        async with pool.acquire() as conn:
            for item in items:
                obs_id = f"obs_{uuid.uuid4().hex[:12]}"
                source_id = self._extract_source_id(source_type, item)
                raw_data = json.dumps(item, ensure_ascii=False)
                lat = item.get("lat")
                lng = item.get(lng_field)
                observed_at = item.get("timestamp") or item.get("time") or now

                if lat is not None and lng is not None:
                    await conn.execute(
                        """INSERT INTO observations (id, source_type, source_id, raw_data, geom, observed_at, created_at)
                           VALUES ($1, $2, $3, $4, ST_SetSRID(ST_MakePoint($5, $6), 4326), $7, $8)""",
                        obs_id, source_type, source_id, raw_data,
                        float(lng), float(lat), str(observed_at), now,
                    )
                else:
                    await conn.execute(
                        """INSERT INTO observations (id, source_type, source_id, raw_data, observed_at, created_at)
                           VALUES ($1, $2, $3, $4, $5, $6)""",
                        obs_id, source_type, source_id, raw_data,
                        str(observed_at), now,
                    )

                inserted.append({
                    "id": obs_id,
                    "source_type": source_type,
                    "source_id": source_id,
                    "raw_data": raw_data,
                })

        return inserted

    @staticmethod
    def _extract_source_id(source_type: str, item: dict) -> str:
        if source_type == "ship":
            return str(item.get("mmsi", item.get("id", "")))
        if source_type == "flight":
            return str(item.get("icao24", item.get("id", "")))
        if source_type == "satellite":
            return str(item.get("norad_id", item.get("id", "")))
        return str(item.get("id", ""))
