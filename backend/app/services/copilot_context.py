from __future__ import annotations

import json
import logging

from app.database import get_pool

logger = logging.getLogger(__name__)


class CopilotContextBuilder:
    async def build(self, scenario_id: str) -> str:
        pool = get_pool()
        async with pool.acquire() as conn:
            scenario = await conn.fetchrow("SELECT * FROM scenarios WHERE id = $1", scenario_id)
            if not scenario:
                return "시나리오를 찾을 수 없습니다."

            seed = await conn.fetchrow(
                "SELECT text, metadata FROM seeds WHERE scenario_id = $1 ORDER BY created_at DESC LIMIT 1",
                scenario_id,
            )

            result = await conn.fetchrow(
                "SELECT status, platform, results, report FROM simulation_results WHERE scenario_id = $1 ORDER BY created_at DESC LIMIT 1",
                scenario_id,
            )

            geo_count = await conn.fetchval(
                "SELECT COUNT(*) FROM geopolitics_events WHERE scenario_id = $1",
                scenario_id,
            )

            obs_count = await conn.fetchval(
                "SELECT COUNT(*) FROM scenario_observations WHERE scenario_id = $1",
                scenario_id,
            )

        parts: list[str] = []

        parts.append(f"## 시나리오: {scenario['name']}")
        parts.append(f"- 지역: {scenario['region_name']}")
        parts.append(f"- 질문: {scenario['question']}")
        parts.append(f"- 상태: {scenario['status']}")
        parts.append(f"- 최대 라운드: {scenario['max_rounds']}")
        parts.append(f"- 관측 데이터: {obs_count}건")

        if seed:
            metadata = json.loads(seed["metadata"]) if seed["metadata"] else {}
            seed_text = seed["text"] or ""
            seed_summary = seed_text[:2000] + ("..." if len(seed_text) > 2000 else "")
            parts.append(f"\n## 시드 문서 (요약)\n{seed_summary}")
            if metadata.get("actors_identified"):
                parts.append(f"- 식별된 행위자: {', '.join(metadata['actors_identified'])}")
            if metadata.get("tension_score"):
                parts.append(f"- 긴장도: {metadata['tension_score']}")

        if result:
            parts.append(f"\n## 시뮬레이션 결과")
            parts.append(f"- 상태: {result['status']}")
            parts.append(f"- 플랫폼: {result['platform']}")
            raw_results = json.loads(result["results"]) if result["results"] else []
            if isinstance(raw_results, dict) and isinstance(raw_results.get("actions"), list):
                actions = raw_results["actions"]
            elif isinstance(raw_results, list):
                actions = raw_results
            else:
                actions = []
            parts.append(f"- 총 액션: {len(actions)}건")

            if actions:
                actor_counts: dict[str, int] = {}
                for act in actions:
                    actor = act.get("actor", act.get("author", "unknown"))
                    actor_counts[actor] = actor_counts.get(actor, 0) + 1
                top_actors = sorted(actor_counts.items(), key=lambda x: -x[1])[:10]
                parts.append(f"- 상위 행위자: {', '.join(f'{a}({c}건)' for a, c in top_actors)}")

            if result["report"]:
                report_summary = result["report"][:1500] + ("..." if len(result["report"]) > 1500 else "")
                parts.append(f"\n## MiroFish 보고서 (요약)\n{report_summary}")

        parts.append(f"\n## 지정학 이벤트: {geo_count}건")

        return "\n".join(parts)
