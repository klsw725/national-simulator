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

            obs_by_source = await conn.fetch(
                """SELECT o.source_type, COUNT(*) as cnt
                   FROM scenario_observations so
                   JOIN observations o ON o.id = so.observation_id
                   WHERE so.scenario_id = $1
                   GROUP BY o.source_type ORDER BY cnt DESC""",
                scenario_id,
            )

            geo_by_type = await conn.fetch(
                "SELECT action_type, COUNT(*) as cnt FROM geopolitics_events WHERE scenario_id = $1 GROUP BY action_type ORDER BY cnt DESC",
                scenario_id,
            )

            geo_top_actors = await conn.fetch(
                "SELECT actor_id, COUNT(*) as cnt FROM geopolitics_events WHERE scenario_id = $1 GROUP BY actor_id ORDER BY cnt DESC LIMIT 10",
                scenario_id,
            )

            geo_by_round = await conn.fetch(
                "SELECT round_number, COUNT(*) as cnt FROM geopolitics_events WHERE scenario_id = $1 GROUP BY round_number ORDER BY round_number",
                scenario_id,
            )

            sample_obs = await conn.fetch(
                """SELECT o.source_type, o.source_id, o.raw_data
                   FROM scenario_observations so
                   JOIN observations o ON o.id = so.observation_id
                   WHERE so.scenario_id = $1
                   ORDER BY o.observed_at DESC LIMIT 15""",
                scenario_id,
            )

        parts: list[str] = []

        parts.append(f"## 시나리오: {scenario['name']}")
        parts.append(f"- 지역: {scenario['region_name']}")
        parts.append(f"- 질문: {scenario['question']}")
        parts.append(f"- 상태: {scenario['status']}")
        parts.append(f"- 최대 라운드: {scenario['max_rounds']}")

        parts.append(f"\n## 관측 데이터: 총 {obs_count}건")
        if obs_by_source:
            for r in obs_by_source:
                parts.append(f"- {r['source_type']}: {r['cnt']}건")

        if sample_obs:
            parts.append("\n## 최근 관측 (샘플)")
            for r in sample_obs:
                raw = json.loads(r["raw_data"]) if r["raw_data"] else {}
                name = raw.get("name", raw.get("callsign", r["source_id"]))
                country = raw.get("country", raw.get("flag", ""))
                lat = raw.get("lat", "")
                lng = raw.get("lng", raw.get("lon", ""))
                line = f"- [{r['source_type']}] {name}"
                if country:
                    line += f" ({country})"
                if lat and lng:
                    line += f" @ {lat},{lng}"
                parts.append(line)

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
                type_counts: dict[str, int] = {}
                round_counts: dict[int, int] = {}
                for act in actions:
                    actor = act.get("actor", act.get("author", "unknown"))
                    actor_counts[actor] = actor_counts.get(actor, 0) + 1
                    atype = act.get("action_type", act.get("type", "unknown"))
                    type_counts[atype] = type_counts.get(atype, 0) + 1
                    rnd = act.get("round", 0)
                    round_counts[rnd] = round_counts.get(rnd, 0) + 1

                top_actors = sorted(actor_counts.items(), key=lambda x: -x[1])[:10]
                parts.append(f"- 상위 행위자: {', '.join(f'{a}({c}건)' for a, c in top_actors)}")

                parts.append(f"\n### 액션 유형 분포")
                for atype, cnt in sorted(type_counts.items(), key=lambda x: -x[1]):
                    parts.append(f"- {atype}: {cnt}건")

                parts.append(f"\n### 라운드별 활동량")
                for rnd, cnt in sorted(round_counts.items()):
                    parts.append(f"- 라운드 {rnd}: {cnt}건")

            if result["report"]:
                report_summary = result["report"][:2000] + ("..." if len(result["report"]) > 2000 else "")
                parts.append(f"\n## 보고서 (요약)\n{report_summary}")

        parts.append(f"\n## 지정학 이벤트: 총 {geo_count}건")
        if geo_by_type:
            parts.append("### 유형별")
            for r in geo_by_type:
                parts.append(f"- {r['action_type']}: {r['cnt']}건")
        if geo_top_actors:
            parts.append("### 주요 행위자")
            for r in geo_top_actors:
                parts.append(f"- {r['actor_id']}: {r['cnt']}건")
        if geo_by_round:
            parts.append("### 라운드별")
            for r in geo_by_round:
                parts.append(f"- 라운드 {r['round_number']}: {r['cnt']}건")

        try:
            from app.causal.domain_dag import build_domain_dag

            dag = build_domain_dag()
            parts.append("\n## 인과 모형 (도메인 DAG)")
            parts.append(f"- 노드: {dag.number_of_nodes()}개 (상태 변수 + 이벤트 타입)")
            parts.append(f"- 엣지: {dag.number_of_edges()}개 (인과 관계)")
            parts.append("- 주요 인과 경로:")
            count = 0
            for u, v, d in dag.edges(data=True):
                if d.get("edge_type") == "propagates_to" and count < 5:
                    strength = d.get("strength", "")
                    parts.append(f"  · {u} → {v} (강도: {strength})")
                    count += 1
            parts.append("- 인과 쿼리 가능: do(변수=값) 개입, 반사실 분석, 인과 귀속")
        except Exception:
            pass

        return "\n".join(parts)
