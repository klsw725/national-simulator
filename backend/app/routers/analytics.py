import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
import asyncpg

from app.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/trend")
async def get_trend(
    source_type: str = Query("ships"),
    hours: int = Query(24, ge=1, le=720),
    interval: str = Query("1h"),
    region: Optional[str] = Query(None),
    conn: asyncpg.Connection = Depends(get_db),
):
    rows = await conn.fetch(
        """SELECT bucket_hour, count, country_breakdown
           FROM osint_metrics_hourly
           WHERE source_type = $1
             AND bucket_hour >= (NOW() - INTERVAL '1 hour' * $2)::text
             AND ($3::text IS NULL OR region_name IS NULL OR region_name = $3)
           ORDER BY bucket_hour""",
        source_type, hours, region,
    )

    data_points = []
    counts = []
    for r in rows:
        count = r["count"]
        counts.append(count)
        countries = json.loads(r["country_breakdown"]) if r["country_breakdown"] else {}
        data_points.append({
            "time": r["bucket_hour"],
            "count": count,
            "countries": countries,
        })

    trend = "stable"
    if len(counts) >= 4:
        first_half = sum(counts[: len(counts) // 2]) / max(len(counts) // 2, 1)
        second_half = sum(counts[len(counts) // 2 :]) / max(len(counts) - len(counts) // 2, 1)
        if second_half > first_half * 1.15:
            trend = "increasing"
        elif second_half < first_half * 0.85:
            trend = "decreasing"

    return {
        "source_type": source_type,
        "interval": interval,
        "data_points": data_points,
        "summary": {
            "min": min(counts) if counts else 0,
            "max": max(counts) if counts else 0,
            "avg": round(sum(counts) / len(counts), 1) if counts else 0,
            "trend": trend,
        },
    }


@router.get("/anomalies")
async def get_anomalies(
    hours: int = Query(24, ge=1, le=168),
    region: Optional[str] = Query(None),
    conn: asyncpg.Connection = Depends(get_db),
):
    from app.services.anomaly_detector import AnomalyDetector

    detector = AnomalyDetector()
    anomalies = await detector.detect(hours=hours, region_name=region)
    return {"anomalies": anomalies}


@router.get("/compare")
async def compare_periods(
    source_type: str = Query("ships"),
    period_a: str = Query(...),
    period_b: str = Query(...),
    hours: int = Query(24, ge=1, le=168),
    conn: asyncpg.Connection = Depends(get_db),
):
    async def get_period_stats(start: str, h: int) -> dict:
        rows = await conn.fetch(
            """SELECT count FROM osint_metrics_hourly
               WHERE source_type = $1
                 AND bucket_hour >= $2
                 AND bucket_hour < ($2::timestamp + INTERVAL '1 hour' * $3)::text
               ORDER BY bucket_hour""",
            source_type, start, h,
        )
        counts = [r["count"] for r in rows]
        if not counts:
            return {"avg": 0, "max": 0, "min": 0, "trend": "no_data", "data_points": 0}

        first_half = sum(counts[: len(counts) // 2]) / max(len(counts) // 2, 1)
        second_half = sum(counts[len(counts) // 2 :]) / max(len(counts) - len(counts) // 2, 1)
        trend = "stable"
        if second_half > first_half * 1.15:
            trend = "increasing"
        elif second_half < first_half * 0.85:
            trend = "decreasing"

        return {
            "avg": round(sum(counts) / len(counts), 1),
            "max": max(counts),
            "min": min(counts),
            "trend": trend,
            "data_points": len(counts),
        }

    stats_a = await get_period_stats(period_a, hours)
    stats_b = await get_period_stats(period_b, hours)

    delta_avg = round(stats_b["avg"] - stats_a["avg"], 1)
    pct_change = (
        f"{(delta_avg / stats_a['avg'] * 100):+.0f}%"
        if stats_a["avg"] > 0
        else "N/A"
    )

    return {
        "source_type": source_type,
        "period_a": stats_a,
        "period_b": stats_b,
        "delta": {
            "avg": delta_avg,
            "max": stats_b["max"] - stats_a["max"],
            "pct_change": pct_change,
        },
    }


@router.get("/snapshots")
async def get_snapshots(
    hours: int = Query(24, ge=1, le=720),
    conn: asyncpg.Connection = Depends(get_db),
):
    rows = await conn.fetch(
        """SELECT snapshot_at, asset_counts, tension_indicators
           FROM osint_snapshots
           WHERE snapshot_at >= (NOW() - INTERVAL '1 hour' * $1)::text
           ORDER BY snapshot_at""",
        hours,
    )

    snapshots = []
    for r in rows:
        snapshots.append({
            "time": r["snapshot_at"],
            "assets": json.loads(r["asset_counts"]) if r["asset_counts"] else {},
            "tension": json.loads(r["tension_indicators"]) if r["tension_indicators"] else {},
        })

    return {"snapshots": snapshots}
