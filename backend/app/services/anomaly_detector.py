from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timezone
from typing import Any

from app.database import get_pool

logger = logging.getLogger(__name__)

ANOMALY_TYPES = {
    "asset_surge": {"sigma_threshold": 2.0, "severity_high": 2.5},
    "asset_departure": {"sigma_threshold": 2.0, "severity_high": 2.5},
    "new_signal": {"severity": "medium"},
    "tension_spike": {"sigma_threshold": 1.5, "severity_high": 2.0},
}


class AnomalyDetector:
    async def detect(self, hours: int = 24, region_name: str | None = None) -> list[dict[str, Any]]:
        anomalies: list[dict[str, Any]] = []

        anomalies.extend(await self._detect_asset_changes(hours, region_name))
        anomalies.extend(await self._detect_new_signals(hours, region_name))
        anomalies.extend(await self._detect_tension_spike(hours))

        anomalies.sort(key=lambda a: (
            0 if a["severity"] == "high" else 1 if a["severity"] == "medium" else 2,
            a["detected_at"],
        ))

        return anomalies

    async def _detect_asset_changes(self, hours: int, region_name: str | None) -> list[dict[str, Any]]:
        pool = get_pool()
        anomalies: list[dict[str, Any]] = []
        now = datetime.now(timezone.utc)

        async with pool.acquire() as conn:
            recent_rows = await conn.fetch(
                """SELECT source_type, bucket_hour, count
                   FROM osint_metrics_hourly
                   WHERE bucket_hour >= (NOW() - INTERVAL '2 hours')::text
                     AND ($1::text IS NULL OR region_name IS NULL OR region_name = $1)
                   ORDER BY source_type, bucket_hour""",
                region_name,
            )

            baseline_rows = await conn.fetch(
                """SELECT source_type, AVG(count) as avg_count, STDDEV(count) as std_count
                   FROM osint_metrics_hourly
                   WHERE bucket_hour >= (NOW() - INTERVAL '7 days')::text
                     AND bucket_hour < (NOW() - INTERVAL '2 hours')::text
                     AND ($1::text IS NULL OR region_name IS NULL OR region_name = $1)
                   GROUP BY source_type""",
                region_name,
            )

        baseline = {r["source_type"]: (r["avg_count"], r["std_count"]) for r in baseline_rows}

        recent_by_source: dict[str, list[int]] = {}
        for r in recent_rows:
            recent_by_source.setdefault(r["source_type"], []).append(r["count"])

        for source_type, counts in recent_by_source.items():
            if source_type not in baseline:
                continue

            avg, std = baseline[source_type]
            if not avg or not std or std == 0:
                continue

            current = max(counts)
            z_score = (current - float(avg)) / float(std)

            if z_score > ANOMALY_TYPES["asset_surge"]["sigma_threshold"]:
                severity = "high" if z_score > ANOMALY_TYPES["asset_surge"]["severity_high"] else "medium"
                anomalies.append({
                    "type": "asset_surge",
                    "source_type": source_type,
                    "detected_at": now.isoformat(),
                    "severity": severity,
                    "detail": f"{source_type} +{current - int(avg)}개 (2h 내). 평균 대비 {z_score:.1f}σ",
                    "current": current,
                    "baseline": round(float(avg), 1),
                    "sigma": round(z_score, 1),
                })
            elif z_score < -ANOMALY_TYPES["asset_departure"]["sigma_threshold"]:
                severity = "high" if z_score < -ANOMALY_TYPES["asset_departure"]["severity_high"] else "medium"
                anomalies.append({
                    "type": "asset_departure",
                    "source_type": source_type,
                    "detected_at": now.isoformat(),
                    "severity": severity,
                    "detail": f"{source_type} {current - int(avg)}개 (2h 내). 평균 대비 {z_score:.1f}σ",
                    "current": current,
                    "baseline": round(float(avg), 1),
                    "sigma": round(z_score, 1),
                })

        return anomalies

    async def _detect_new_signals(self, hours: int, region_name: str | None) -> list[dict[str, Any]]:
        pool = get_pool()
        anomalies: list[dict[str, Any]] = []
        now = datetime.now(timezone.utc)

        signal_sources = ["gps_jamming", "internet_outages", "firms_fires"]

        async with pool.acquire() as conn:
            for source in signal_sources:
                recent = await conn.fetchval(
                    """SELECT count FROM osint_metrics_hourly
                       WHERE source_type = $1
                         AND bucket_hour >= (NOW() - INTERVAL '2 hours')::text
                       ORDER BY bucket_hour DESC LIMIT 1""",
                    source,
                )

                baseline = await conn.fetchval(
                    """SELECT AVG(count) FROM osint_metrics_hourly
                       WHERE source_type = $1
                         AND bucket_hour >= (NOW() - INTERVAL '7 days')::text
                         AND bucket_hour < (NOW() - INTERVAL '2 hours')::text""",
                    source,
                )

                if recent and recent > 0 and (not baseline or float(baseline) < 0.5):
                    anomalies.append({
                        "type": "new_signal",
                        "source_type": source,
                        "detected_at": now.isoformat(),
                        "severity": "medium",
                        "detail": f"신규 {source} 감지 ({recent}건)",
                        "current": recent,
                        "baseline": 0,
                        "sigma": 0,
                    })

        return anomalies

    async def _detect_tension_spike(self, hours: int) -> list[dict[str, Any]]:
        pool = get_pool()
        anomalies: list[dict[str, Any]] = []
        now = datetime.now(timezone.utc)

        async with pool.acquire() as conn:
            recent_snap = await conn.fetchrow(
                """SELECT tension_indicators FROM osint_snapshots
                   WHERE snapshot_at >= (NOW() - INTERVAL '2 hours')::text
                   ORDER BY snapshot_at DESC LIMIT 1"""
            )

            baseline_snaps = await conn.fetch(
                """SELECT tension_indicators FROM osint_snapshots
                   WHERE snapshot_at >= (NOW() - INTERVAL '7 days')::text
                     AND snapshot_at < (NOW() - INTERVAL '2 hours')::text"""
            )

        if not recent_snap or not baseline_snaps:
            return anomalies

        recent_tension = json.loads(recent_snap["tension_indicators"] or "{}")
        gdelt_current = recent_tension.get("gdelt_avg", 0)

        gdelt_values = []
        for snap in baseline_snaps:
            indicators = json.loads(snap["tension_indicators"] or "{}")
            val = indicators.get("gdelt_avg", 0)
            if val:
                gdelt_values.append(float(val))

        if len(gdelt_values) < 3:
            return anomalies

        avg = sum(gdelt_values) / len(gdelt_values)
        variance = sum((v - avg) ** 2 for v in gdelt_values) / len(gdelt_values)
        std = math.sqrt(variance) if variance > 0 else 0

        if std == 0:
            return anomalies

        z_score = (float(gdelt_current) - avg) / std

        if z_score > ANOMALY_TYPES["tension_spike"]["sigma_threshold"]:
            severity = "high" if z_score > ANOMALY_TYPES["tension_spike"]["severity_high"] else "medium"
            anomalies.append({
                "type": "tension_spike",
                "source_type": "gdelt",
                "detected_at": now.isoformat(),
                "severity": severity,
                "detail": f"GDELT 긴장도 {gdelt_current:.1f} (7일 평균 {avg:.1f} 대비 {z_score:.1f}σ)",
                "current": round(float(gdelt_current), 1),
                "baseline": round(avg, 1),
                "sigma": round(z_score, 1),
            })

        return anomalies
