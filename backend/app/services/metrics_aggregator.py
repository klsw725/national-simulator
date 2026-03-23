from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from app.database import get_pool

logger = logging.getLogger(__name__)

SOURCE_TYPES = [
    "ships", "military_flights", "satellites", "uavs", "tracked_flights",
    "cctv", "kiwisdr", "gps_jamming", "earthquakes", "firms_fires",
    "power_plants", "datacenters", "internet_outages", "military_bases",
]


class MetricsAggregator:
    async def aggregate_hourly(self, hour: str, region_name: str | None = None) -> int:
        pool = get_pool()
        inserted = 0

        async with pool.acquire() as conn:
            for source_type in SOURCE_TYPES:
                row = await conn.fetchrow(
                    """SELECT
                         COUNT(DISTINCT source_id) as entity_count
                       FROM observations
                       WHERE source_type = $1
                         AND observed_at >= $2
                         AND observed_at < ($2::timestamp + interval '1 hour')::text""",
                    source_type, hour,
                )

                count = row["entity_count"] if row else 0
                if count == 0:
                    continue

                country_rows = await conn.fetch(
                    """SELECT
                         raw_data
                       FROM observations
                       WHERE source_type = $1
                         AND observed_at >= $2
                         AND observed_at < ($2::timestamp + interval '1 hour')::text""",
                    source_type, hour,
                )

                country_counts: dict[str, int] = {}
                for r in country_rows:
                    raw = json.loads(r["raw_data"]) if r["raw_data"] else {}
                    country = raw.get("country", "unknown")
                    if country:
                        country_counts[country] = country_counts.get(country, 0) + 1

                metric_id = f"met_{uuid.uuid4().hex[:12]}"
                now = datetime.now(timezone.utc).isoformat()

                await conn.execute(
                    """INSERT INTO osint_metrics_hourly (id, source_type, bucket_hour, region_name, count, country_breakdown, created_at)
                       VALUES ($1, $2, $3, $4, $5, $6, $7)
                       ON CONFLICT (id) DO NOTHING""",
                    metric_id, source_type, hour, region_name, count,
                    json.dumps(country_counts, ensure_ascii=False), now,
                )
                inserted += 1

        return inserted

    async def create_snapshot(self, asset_counts: dict[str, int], tension_indicators: dict[str, float]) -> str:
        pool = get_pool()
        snap_id = f"snap_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()

        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO osint_snapshots (id, snapshot_at, asset_counts, tension_indicators, created_at)
                   VALUES ($1, $2, $3, $4, $5)""",
                snap_id, now,
                json.dumps(asset_counts, ensure_ascii=False),
                json.dumps(tension_indicators, ensure_ascii=False),
                now,
            )

        return snap_id

    async def cleanup_old_data(self, observations_days: int = 7, metrics_days: int = 90, snapshots_days: int = 30) -> dict[str, int]:
        pool = get_pool()
        deleted = {}

        async with pool.acquire() as conn:
            result = await conn.execute(
                f"DELETE FROM observations WHERE created_at < (NOW() - INTERVAL '{observations_days} days')::text"
            )
            deleted["observations"] = int(result.split()[-1]) if result else 0

            result = await conn.execute(
                f"DELETE FROM osint_metrics_hourly WHERE created_at < (NOW() - INTERVAL '{metrics_days} days')::text"
            )
            deleted["metrics"] = int(result.split()[-1]) if result else 0

            result = await conn.execute(
                f"DELETE FROM osint_snapshots WHERE created_at < (NOW() - INTERVAL '{snapshots_days} days')::text"
            )
            deleted["snapshots"] = int(result.split()[-1]) if result else 0

        return deleted
