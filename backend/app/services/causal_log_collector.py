from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd

from app.database import get_pool
TENSION_KEYWORDS_TYPE = frozenset(
    ("military", "threat", "attack", "sanction", "blockade"),
)
TENSION_KEYWORDS_CONTENT = (
    "전쟁", "공격", "위협", "제재", "봉쇄",
    "war", "attack", "threat", "sanction",
)

_ESCALATION_EVENT_TYPES = frozenset(
    ("military_movement", "military_exercise", "sanction_impose", "trade_restriction"),
)


def _to_round_num(item: dict) -> int:
    for key in ("round", "round_num", "round_number"):
        value = item.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return 0


def _parse_actions(raw_results: str | None) -> list[dict]:
    if not raw_results:
        return []
    parsed = json.loads(raw_results)
    if isinstance(parsed, dict) and isinstance(parsed.get("actions"), list):
        return parsed["actions"]
    if isinstance(parsed, list):
        return parsed
    return []


class CausalLogCollector:
    async def collect_from_result(self, scenario_id: str, result_id: str) -> int:
        pool = get_pool()
        async with pool.acquire() as conn:
            sim_row = await conn.fetchrow(
                "SELECT results FROM simulation_results WHERE id = $1 AND scenario_id = $2",
                result_id,
                scenario_id,
            )
            if not sim_row:
                return 0

            actions = _parse_actions(sim_row["results"])
            geo_rows = await conn.fetch(
                """SELECT action_type, round_number
                   FROM geopolitics_events
                   WHERE scenario_id = $1 AND simulation_result_id = $2""",
                scenario_id,
                result_id,
            )

            geo_by_round: dict[int, list[str]] = {}
            for row in geo_rows:
                rn = int(row["round_number"] or 0)
                geo_by_round.setdefault(rn, []).append((row["action_type"] or "").lower())

            actions_by_round: dict[int, list[dict]] = {}
            all_action_types: set[str] = set()
            for action in actions:
                rn = _to_round_num(action)
                actions_by_round.setdefault(rn, []).append(action)
                action_type = (action.get("action_type") or action.get("type") or "").lower()
                if action_type:
                    all_action_types.add(action_type)

            total_possible_action_types = max(len(all_action_types), 1)
            round_numbers = sorted(set(actions_by_round.keys()) | set(geo_by_round.keys()))

            now = datetime.now(timezone.utc).isoformat()
            payloads: list[tuple[str, str, int, str, str]] = []

            for round_num in round_numbers:
                round_actions = actions_by_round.get(round_num, [])
                round_geo = geo_by_round.get(round_num, [])

                tension_signals = 0
                for action in round_actions:
                    action_type = (action.get("action_type") or action.get("type") or "").lower()
                    content = (action.get("content") or action.get("text") or "").lower()
                    if action_type in TENSION_KEYWORDS_TYPE:
                        tension_signals += 1
                    elif any(keyword in content for keyword in TENSION_KEYWORDS_CONTENT):
                        tension_signals += 1

                unique_action_types = {
                    (action.get("action_type") or action.get("type") or "").lower()
                    for action in round_actions
                    if (action.get("action_type") or action.get("type") or "")
                }
                unique_agents = {
                    (action.get("agent_name") or action.get("actor") or action.get("author") or "")
                    for action in round_actions
                    if (action.get("agent_name") or action.get("actor") or action.get("author") or "")
                }
                escalation_count = sum(1 for event_type in round_geo if event_type in _ESCALATION_EVENT_TYPES)

                total_actions = len(round_actions)
                total_geo = len(round_geo)
                variables = {
                    "tension_ratio": round(tension_signals / total_actions, 4) if total_actions else 0.0,
                    "action_diversity": round(len(unique_action_types) / total_possible_action_types, 4),
                    "actor_activity": float(len(unique_agents)),
                    "geo_event_count": float(total_geo),
                    "escalation_level": round(escalation_count / total_geo, 4) if total_geo else 0.0,
                }
                payloads.append((scenario_id, result_id, round_num, json.dumps(variables), now))

            if not payloads:
                return 0

            await conn.executemany(
                """INSERT INTO causal_observations
                   (scenario_id, result_id, round_num, variables, created_at)
                   VALUES ($1, $2, $3, $4::jsonb, $5)""",
                payloads,
            )

            return len(payloads)

    async def build_dataframe(self, scenario_id: str, min_results: int = 5) -> pd.DataFrame | None:
        pool = get_pool()
        async with pool.acquire() as conn:
            result_count = await conn.fetchval(
                "SELECT COUNT(DISTINCT result_id) FROM causal_observations WHERE scenario_id = $1",
                scenario_id,
            )
            if (result_count or 0) < min_results:
                return None

            rows = await conn.fetch(
                """SELECT result_id, round_num, variables
                   FROM causal_observations
                   WHERE scenario_id = $1
                   ORDER BY result_id, round_num""",
                scenario_id,
            )

        records: list[dict] = []
        for row in rows:
            raw_variables = row["variables"]
            variables = dict(raw_variables) if isinstance(raw_variables, dict) else json.loads(raw_variables)
            records.append(
                {
                    "result_id": row["result_id"],
                    "round_num": row["round_num"],
                    **variables,
                },
            )

        if len(records) < min_results:
            return None

        return pd.DataFrame.from_records(records)
