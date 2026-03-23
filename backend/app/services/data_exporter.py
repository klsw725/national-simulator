from __future__ import annotations

import csv
import io
import json
import logging
from typing import Any

import asyncpg

from app.database import get_pool

logger = logging.getLogger(__name__)


class DataExporter:
    async def export_scenario_json(self, scenario_id: str) -> dict[str, Any]:
        pool = get_pool()
        async with pool.acquire() as conn:
            scenario = await conn.fetchrow("SELECT * FROM scenarios WHERE id = $1", scenario_id)
            if not scenario:
                raise ValueError(f"Scenario {scenario_id} not found")

            seed = await conn.fetchrow(
                "SELECT id, text, metadata, created_at FROM seeds WHERE scenario_id = $1 ORDER BY created_at DESC LIMIT 1",
                scenario_id,
            )

            result = await conn.fetchrow(
                "SELECT id, status, platform, results, report, created_at, completed_at FROM simulation_results WHERE scenario_id = $1 ORDER BY created_at DESC LIMIT 1",
                scenario_id,
            )

            geo_rows = await conn.fetch(
                "SELECT action_type, actor_id, target_actor_ids, content, magnitude, round_number, event_at FROM geopolitics_events WHERE scenario_id = $1 ORDER BY round_number, event_at",
                scenario_id,
            )

            obs_rows = await conn.fetch(
                """SELECT o.source_type, o.source_id, o.raw_data, o.observed_at, so.used_in_seed
                   FROM scenario_observations so
                   LEFT JOIN observations o ON o.id = so.observation_id
                   WHERE so.scenario_id = $1
                   ORDER BY o.observed_at""",
                scenario_id,
            )

        return {
            "scenario": {
                "id": scenario["id"],
                "name": scenario["name"],
                "region_name": scenario["region_name"],
                "region_bbox": json.loads(scenario["region_bbox"]) if scenario["region_bbox"] else [],
                "question": scenario["question"],
                "max_rounds": scenario["max_rounds"],
                "simulation_params": json.loads(scenario["simulation_params"]) if scenario["simulation_params"] else {},
                "status": scenario["status"],
                "created_at": scenario["created_at"],
            },
            "seed": {
                "text": seed["text"] if seed else None,
                "metadata": json.loads(seed["metadata"]) if seed and seed["metadata"] else {},
            } if seed else None,
            "simulation": {
                "status": result["status"] if result else None,
                "platform": result["platform"] if result else None,
                "results": json.loads(result["results"]) if result and result["results"] else None,
                "report": result["report"] if result else None,
                "completed_at": result["completed_at"] if result else None,
            } if result else None,
            "geopolitics_events": [
                {
                    "action_type": r["action_type"],
                    "actor_id": r["actor_id"],
                    "target_actor_ids": json.loads(r["target_actor_ids"]) if r["target_actor_ids"] else [],
                    "content": r["content"],
                    "magnitude": r["magnitude"],
                    "round_number": r["round_number"],
                    "event_at": r["event_at"],
                }
                for r in geo_rows
            ],
            "observations_count": len(obs_rows),
        }

    async def export_actions_csv(self, scenario_id: str) -> str:
        pool = get_pool()
        async with pool.acquire() as conn:
            result = await conn.fetchrow(
                "SELECT results FROM simulation_results WHERE scenario_id = $1 ORDER BY created_at DESC LIMIT 1",
                scenario_id,
            )

        if not result or not result["results"]:
            return ""

        actions = json.loads(result["results"])
        if not isinstance(actions, list) or not actions:
            return ""

        output = io.StringIO()
        fields = ["round", "platform", "actor", "action_type", "content", "timestamp"]
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for action in actions:
            writer.writerow({
                "round": action.get("round", ""),
                "platform": action.get("platform", ""),
                "actor": action.get("actor", action.get("author", "")),
                "action_type": action.get("action_type", action.get("type", "")),
                "content": action.get("content", action.get("text", "")),
                "timestamp": action.get("timestamp", action.get("created_at", "")),
            })
        return output.getvalue()

    async def export_observations_csv(self, scenario_id: str) -> str:
        pool = get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT o.source_type, o.source_id, o.raw_data, o.observed_at, so.used_in_seed
                   FROM scenario_observations so
                   LEFT JOIN observations o ON o.id = so.observation_id
                   WHERE so.scenario_id = $1
                   ORDER BY o.observed_at""",
                scenario_id,
            )

        if not rows:
            return ""

        output = io.StringIO()
        fields = ["source_type", "source_id", "observed_at", "used_in_seed", "lat", "lng"]
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            raw = json.loads(r["raw_data"]) if r["raw_data"] else {}
            writer.writerow({
                "source_type": r["source_type"],
                "source_id": r["source_id"],
                "observed_at": r["observed_at"],
                "used_in_seed": r["used_in_seed"],
                "lat": raw.get("lat", ""),
                "lng": raw.get("lng", raw.get("lon", "")),
            })
        return output.getvalue()

    async def export_geopolitics_csv(self, scenario_id: str) -> str:
        pool = get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT action_type, actor_id, target_actor_ids, content, magnitude, round_number, event_at FROM geopolitics_events WHERE scenario_id = $1 ORDER BY round_number, event_at",
                scenario_id,
            )

        if not rows:
            return ""

        output = io.StringIO()
        fields = ["round_number", "action_type", "actor_id", "target_actor_ids", "content", "magnitude", "event_at"]
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow({
                "round_number": r["round_number"],
                "action_type": r["action_type"],
                "actor_id": r["actor_id"],
                "target_actor_ids": r["target_actor_ids"] or "[]",
                "content": r["content"],
                "magnitude": r["magnitude"],
                "event_at": r["event_at"],
            })
        return output.getvalue()

    async def export_report_markdown(self, scenario_id: str) -> str:
        pool = get_pool()
        async with pool.acquire() as conn:
            result = await conn.fetchrow(
                "SELECT report FROM simulation_results WHERE scenario_id = $1 ORDER BY created_at DESC LIMIT 1",
                scenario_id,
            )
        return result["report"] if result and result["report"] else ""
