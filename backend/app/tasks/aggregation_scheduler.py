from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta

from app.services.metrics_aggregator import MetricsAggregator

logger = logging.getLogger(__name__)

HOURLY_INTERVAL = 3600
CLEANUP_INTERVAL = 86400


async def run_hourly_aggregation():
    aggregator = MetricsAggregator()
    while True:
        try:
            now = datetime.now(timezone.utc)
            prev_hour = (now - timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
            hour_str = prev_hour.isoformat()

            inserted = await aggregator.aggregate_hourly(hour_str)
            if inserted > 0:
                logger.info("Hourly aggregation: %d metrics for %s", inserted, hour_str)
        except Exception:
            logger.exception("Hourly aggregation failed")

        await asyncio.sleep(HOURLY_INTERVAL)


async def run_daily_cleanup():
    aggregator = MetricsAggregator()
    while True:
        try:
            deleted = await aggregator.cleanup_old_data()
            total = sum(deleted.values())
            if total > 0:
                logger.info("Daily cleanup: %s", deleted)
        except Exception:
            logger.exception("Daily cleanup failed")

        await asyncio.sleep(CLEANUP_INTERVAL)


def start_background_tasks():
    asyncio.create_task(run_hourly_aggregation())
    asyncio.create_task(run_daily_cleanup())
    logger.info("Analytics background tasks started")
