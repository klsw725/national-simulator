from __future__ import annotations

import json
import logging
from typing import Any

from app.database import get_pool

logger = logging.getLogger(__name__)

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_observations",
            "description": "관측 데이터를 소스 유형으로 검색합니다. ships, flights, satellites, gdelt 등.",
            "parameters": {
                "type": "object",
                "properties": {
                    "scenario_id": {"type": "string"},
                    "source_type": {"type": "string", "description": "ships, military_flights, satellites, gdelt, uavs, cctv, kiwisdr 등"},
                    "limit": {"type": "integer", "default": 20},
                },
                "required": ["scenario_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "count_entities",
            "description": "시나리오 관측에서 엔티티(선박, 항공기, 위성 등)를 소스 유형별로 집계합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "scenario_id": {"type": "string"},
                },
                "required": ["scenario_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_simulation_actions",
            "description": "시뮬레이션 액션을 분석합니다. 행위자별 액션 수, 유형별 분포, 라운드별 활동량을 반환합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "scenario_id": {"type": "string"},
                },
                "required": ["scenario_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_geopolitics_summary",
            "description": "시나리오의 지정학 이벤트 요약을 반환합니다. 유형별 분포, 주요 행위자, 라운드별 이벤트 수를 포함합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "scenario_id": {"type": "string"},
                },
                "required": ["scenario_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_scenarios",
            "description": "2개 시나리오의 시뮬레이션 결과를 비교합니다. 행위자, 액션 수, 지정학 이벤트 차이를 분석합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "scenario_id_a": {"type": "string"},
                    "scenario_id_b": {"type": "string"},
                },
                "required": ["scenario_id_a", "scenario_id_b"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "suggest_whatif",
            "description": "현재 시나리오를 기반으로 What-If 시나리오 변형 파라미터를 제안합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "scenario_id": {"type": "string"},
                    "hypothesis": {"type": "string", "description": "분석관이 탐색하려는 가정"},
                },
                "required": ["scenario_id", "hypothesis"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_summary",
            "description": "시뮬레이션 결과의 핵심 발견 3-5개를 추출하여 요약합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "scenario_id": {"type": "string"},
                },
                "required": ["scenario_id"],
            },
        },
    },
]


async def execute_tool(name: str, args: dict[str, Any]) -> str:
    try:
        if name == "search_observations":
            return await _search_observations(**args)
        elif name == "count_entities":
            return await _count_entities(**args)
        elif name == "analyze_simulation_actions":
            return await _analyze_simulation_actions(**args)
        elif name == "get_geopolitics_summary":
            return await _get_geopolitics_summary(**args)
        elif name == "compare_scenarios":
            return await _compare_scenarios(**args)
        elif name == "suggest_whatif":
            return await _suggest_whatif(**args)
        elif name == "generate_summary":
            return await _generate_summary(**args)
        else:
            return json.dumps({"error": f"Unknown tool: {name}"})
    except Exception as e:
        logger.exception("Tool execution failed: %s", name)
        return json.dumps({"error": str(e)})


async def _search_observations(scenario_id: str, source_type: str | None = None, limit: int = 20) -> str:
    pool = get_pool()
    async with pool.acquire() as conn:
        if source_type:
            rows = await conn.fetch(
                """SELECT o.source_type, o.source_id, o.raw_data, o.observed_at
                   FROM scenario_observations so
                   JOIN observations o ON o.id = so.observation_id
                   WHERE so.scenario_id = $1 AND o.source_type = $2
                   ORDER BY o.observed_at DESC LIMIT $3""",
                scenario_id, source_type, limit,
            )
        else:
            rows = await conn.fetch(
                """SELECT o.source_type, o.source_id, o.raw_data, o.observed_at
                   FROM scenario_observations so
                   JOIN observations o ON o.id = so.observation_id
                   WHERE so.scenario_id = $1
                   ORDER BY o.observed_at DESC LIMIT $2""",
                scenario_id, limit,
            )
    results = []
    for r in rows:
        raw = json.loads(r["raw_data"]) if r["raw_data"] else {}
        results.append({
            "source_type": r["source_type"],
            "source_id": r["source_id"],
            "observed_at": r["observed_at"],
            "name": raw.get("name", raw.get("callsign", "")),
            "country": raw.get("country", ""),
            "lat": raw.get("lat"),
            "lng": raw.get("lng", raw.get("lon")),
        })
    return json.dumps({"count": len(results), "observations": results}, ensure_ascii=False)


async def _count_entities(scenario_id: str) -> str:
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT o.source_type, COUNT(*) as cnt
               FROM scenario_observations so
               JOIN observations o ON o.id = so.observation_id
               WHERE so.scenario_id = $1
               GROUP BY o.source_type ORDER BY cnt DESC""",
            scenario_id,
        )
    counts = {r["source_type"]: r["cnt"] for r in rows}
    total = sum(counts.values())
    return json.dumps({"total": total, "by_source": counts}, ensure_ascii=False)


async def _analyze_simulation_actions(scenario_id: str) -> str:
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.fetchrow(
            "SELECT results FROM simulation_results WHERE scenario_id = $1 ORDER BY created_at DESC LIMIT 1",
            scenario_id,
        )
    if not result or not result["results"]:
        return json.dumps({"error": "시뮬레이션 결과 없음"})

    actions = json.loads(result["results"])
    actor_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    round_counts: dict[int, int] = {}

    for act in actions:
        actor = act.get("actor", act.get("author", "unknown"))
        actor_counts[actor] = actor_counts.get(actor, 0) + 1
        atype = act.get("action_type", act.get("type", "unknown"))
        type_counts[atype] = type_counts.get(atype, 0) + 1
        rnd = act.get("round", 0)
        round_counts[rnd] = round_counts.get(rnd, 0) + 1

    return json.dumps({
        "total_actions": len(actions),
        "by_actor": dict(sorted(actor_counts.items(), key=lambda x: -x[1])),
        "by_type": dict(sorted(type_counts.items(), key=lambda x: -x[1])),
        "by_round": dict(sorted(round_counts.items())),
    }, ensure_ascii=False)


async def _get_geopolitics_summary(scenario_id: str) -> str:
    pool = get_pool()
    async with pool.acquire() as conn:
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM geopolitics_events WHERE scenario_id = $1", scenario_id)
        type_rows = await conn.fetch(
            "SELECT action_type, COUNT(*) as cnt FROM geopolitics_events WHERE scenario_id = $1 GROUP BY action_type ORDER BY cnt DESC",
            scenario_id,
        )
        actor_rows = await conn.fetch(
            "SELECT actor_id, COUNT(*) as cnt FROM geopolitics_events WHERE scenario_id = $1 GROUP BY actor_id ORDER BY cnt DESC LIMIT 10",
            scenario_id,
        )
        round_rows = await conn.fetch(
            "SELECT round_number, COUNT(*) as cnt FROM geopolitics_events WHERE scenario_id = $1 GROUP BY round_number ORDER BY round_number",
            scenario_id,
        )
    return json.dumps({
        "total_events": total,
        "by_type": {r["action_type"]: r["cnt"] for r in type_rows},
        "top_actors": {r["actor_id"]: r["cnt"] for r in actor_rows},
        "by_round": {r["round_number"]: r["cnt"] for r in round_rows},
    }, ensure_ascii=False)


async def _compare_scenarios(scenario_id_a: str, scenario_id_b: str) -> str:
    from app.services.scenario_comparator import ScenarioComparator
    result = await ScenarioComparator().compare(scenario_id_a, scenario_id_b)
    return json.dumps(result, ensure_ascii=False)


async def _suggest_whatif(scenario_id: str, hypothesis: str) -> str:
    pool = get_pool()
    async with pool.acquire() as conn:
        scenario = await conn.fetchrow("SELECT name, region_name, question FROM scenarios WHERE id = $1", scenario_id)
    if not scenario:
        return json.dumps({"error": "시나리오를 찾을 수 없습니다"})

    return json.dumps({
        "base_scenario": scenario["name"],
        "hypothesis": hypothesis,
        "suggested_params": {
            "name": f"What-If: {hypothesis[:50]}",
            "region": scenario["region_name"],
            "question": f"{scenario['question']} — What-If: {hypothesis}",
            "max_rounds": 10,
        },
    }, ensure_ascii=False)


async def _generate_summary(scenario_id: str) -> str:
    pool = get_pool()
    async with pool.acquire() as conn:
        scenario = await conn.fetchrow("SELECT name, question FROM scenarios WHERE id = $1", scenario_id)
        result = await conn.fetchrow(
            "SELECT results, report FROM simulation_results WHERE scenario_id = $1 ORDER BY created_at DESC LIMIT 1",
            scenario_id,
        )
        geo_count = await conn.fetchval(
            "SELECT COUNT(*) FROM geopolitics_events WHERE scenario_id = $1", scenario_id)

    actions = json.loads(result["results"]) if result and result["results"] else []
    actors = set()
    for act in actions:
        actor = act.get("actor", act.get("author", ""))
        if actor:
            actors.add(actor)

    report_excerpt = ""
    if result and result["report"]:
        report_excerpt = result["report"][:1000]

    return json.dumps({
        "scenario": scenario["name"] if scenario else "unknown",
        "question": scenario["question"] if scenario else "",
        "total_actions": len(actions),
        "unique_actors": len(actors),
        "actors": sorted(actors),
        "geopolitics_events": geo_count,
        "report_excerpt": report_excerpt,
    }, ensure_ascii=False)
