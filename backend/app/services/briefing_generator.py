from __future__ import annotations

import json
import logging
import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from openai import AsyncOpenAI

from app.clients.shadowbroker import BBox, ShadowBrokerClient
from app.config import settings
from app.database import get_pool

logger = logging.getLogger(__name__)

BRIEFING_PROMPT = """\
당신은 지정학 위기 브리핑 작성 전문가입니다.
아래 입력 데이터를 기반으로 의사결정자를 위한 브리핑 문서를 한국어 마크다운으로 작성하세요.

## 시나리오 기본 정보
- 시나리오명: {scenario_name}
- 지역: {region_name}
- 핵심 질문: {question}

## 시드 상황 분석
{seed_text}

## 시뮬레이션 액션 요약
{simulation_summary}

## 지정학 이벤트 요약
{geopolitics_summary}

## MiroFish 보고서
{report_text}

{current_osint_section}
다음 구조를 정확히 따라 작성하세요:

# 상황 브리핑: [시나리오명]
## 1. 상황 요약
## 2. 핵심 발견 (3-5개)
## 3. 행위자 분석
## 4. 시뮬레이션 결과 요약
## 5. 지정학적 함의
## 6. 권장 조치
## 7. 현재 상황 대비 변화 (시드 생성 이후)
## 부록: 데이터 소스, 방법론, 신뢰도

요구사항:
- 과장 없이 근거 중심으로 작성하세요.
- 수치/사실이 없는 경우 추측하지 말고 "데이터 제한"을 명시하세요.
- 정책 결정자가 바로 읽을 수 있도록 간결하게 작성하세요.
- "## 7. 현재 상황 대비 변화"에서는 시드 생성 시점의 데이터와 현재 OSINT 데이터를 비교 분석하세요.
  현재 OSINT 데이터가 없는 경우 해당 섹션을 "데이터 없음"으로 표기하세요.
"""


class BriefingGenerator:
    def __init__(self, sb_client: ShadowBrokerClient | None = None):
        self._sb = sb_client
        self._llm = AsyncOpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )

    async def _collect_current_osint(self, bbox: list[float]) -> str:
        if not self._sb or len(bbox) < 4:
            return ""
        try:
            sb_bbox = BBox(s=bbox[1], w=bbox[0], n=bbox[3], e=bbox[2])
            fast_data = await self._sb.get_fast_data(sb_bbox)
            slow_data = await self._sb.get_slow_data(sb_bbox)

            min_lng, min_lat, max_lng, max_lat = bbox

            def _in_bbox(item: dict, lng_key: str = "lng") -> bool:
                lat = item.get("lat")
                lng = item.get(lng_key)
                if lat is None or lng is None:
                    return False
                return min_lat <= lat <= max_lat and min_lng <= lng <= max_lng

            ships = [s for s in fast_data.get("ships", []) if _in_bbox(s)]
            mil_flights = [f for f in fast_data.get("military_flights", []) if _in_bbox(f)]
            uavs = [u for u in fast_data.get("uavs", []) if _in_bbox(u)]
            satellites = [s for s in fast_data.get("satellites", []) if _in_bbox(s)]
            gps_jamming = [j for j in fast_data.get("gps_jamming", []) if _in_bbox(j)]
            bases = [b for b in slow_data.get("military_bases", []) if _in_bbox(b)]

            lines = [
                f"- 군함: {len(ships)}척",
                f"- 군용기: {len(mil_flights)}대",
                f"- UAV: {len(uavs)}대",
                f"- 정찰위성: {len(satellites)}기",
                f"- 군사기지: {len(bases)}개",
            ]
            if gps_jamming:
                lines.append(f"- GPS 교란: {len(gps_jamming)}건")

            gdelt = slow_data.get("gdelt", [])
            headlines: list[str] = []
            for feature in gdelt:
                coords = feature.get("geometry", {}).get("coordinates", [])
                if len(coords) >= 2:
                    lng, lat = coords[0], coords[1]
                    if not (min_lat <= lat <= max_lat and min_lng <= lng <= max_lng):
                        continue
                for h in feature.get("properties", {}).get("_headlines_list", [])[:2]:
                    if h and h not in headlines:
                        headlines.append(h)
            if headlines:
                lines.append("- GDELT 주요 뉴스:")
                for h in headlines[:5]:
                    lines.append(f"  - {h}")

            news = slow_data.get("news", [])
            bbox_news = [n for n in news if _in_bbox(n)]
            bbox_news.sort(key=lambda n: n.get("risk_score", 0), reverse=True)
            if bbox_news:
                lines.append("- 최신 뉴스:")
                for item in bbox_news[:3]:
                    title = item.get("title", "")
                    source = item.get("source", "")
                    if title:
                        lines.append(f"  - [{source}] {title}")

            now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            return f"(데이터 기준: {now})\n" + "\n".join(lines)
        except Exception:
            logger.warning("Failed to collect current OSINT for briefing")
            return "(현재 OSINT 데이터 수집 실패 — ShadowBroker 연결 불가)"

    def _summarize_simulation_actions(self, results_raw: str | None) -> str:
        if not results_raw:
            return "시뮬레이션 액션 데이터 없음"

        try:
            parsed = json.loads(results_raw)
        except json.JSONDecodeError:
            return "시뮬레이션 액션 데이터 파싱 실패"

        actions: list[dict[str, Any]] = []
        if isinstance(parsed, dict) and isinstance(parsed.get("actions"), list):
            actions = [a for a in parsed["actions"] if isinstance(a, dict)]
        elif isinstance(parsed, list):
            actions = [a for a in parsed if isinstance(a, dict)]

        if not actions:
            return "시뮬레이션 액션 없음"

        actor_counter: Counter[str] = Counter()
        action_counter: Counter[str] = Counter()
        key_events: list[str] = []

        for action in actions:
            actor = action.get("agent_name") or action.get("actor_id") or "unknown"
            action_type = action.get("action_type") or "unknown"
            actor_counter[str(actor)] += 1
            action_counter[str(action_type)] += 1

            event_text = (
                action.get("content")
                or action.get("post_content")
                or action.get("text")
                or ""
            )
            if event_text and event_text not in key_events and len(key_events) < 5:
                key_events.append(str(event_text).strip().replace("\n", " ")[:180])

        actor_summary = ", ".join(
            f"{actor} {count}건" for actor, count in actor_counter.most_common(8)
        )
        action_summary = ", ".join(
            f"{action_type} {count}건"
            for action_type, count in action_counter.most_common(8)
        )

        lines = [
            f"- 총 액션 수: {len(actions)}건",
            f"- 행위자별 액션: {actor_summary or '없음'}",
            f"- 액션 유형 분포: {action_summary or '없음'}",
        ]
        if key_events:
            lines.append("- 주요 이벤트:")
            lines.extend(f"  - {event}" for event in key_events)

        return "\n".join(lines)

    def _summarize_geopolitics_events(self, rows: list[Any]) -> str:
        if not rows:
            return "지정학 이벤트 데이터 없음"

        actor_counter: Counter[str] = Counter()
        action_counter: Counter[str] = Counter()
        key_events: list[str] = []

        for row in rows:
            actor = row.get("actor_id") or "unknown"
            action_type = row.get("action_type") or "unknown"
            actor_counter[str(actor)] += 1
            action_counter[str(action_type)] += 1

            content = row.get("content")
            if content and content not in key_events and len(key_events) < 5:
                key_events.append(str(content).strip().replace("\n", " ")[:180])

        actor_summary = ", ".join(
            f"{actor} {count}건" for actor, count in actor_counter.most_common(8)
        )
        action_summary = ", ".join(
            f"{action_type} {count}건"
            for action_type, count in action_counter.most_common(8)
        )

        lines = [
            f"- 총 이벤트 수: {len(rows)}건",
            f"- 행위자별 이벤트: {actor_summary or '없음'}",
            f"- 이벤트 유형 분포: {action_summary or '없음'}",
        ]
        if key_events:
            lines.append("- 주요 이벤트:")
            lines.extend(f"  - {event}" for event in key_events)

        return "\n".join(lines)

    async def _call_llm(self, prompt: str) -> str:
        response = await self._llm.chat.completions.create(
            model=settings.llm_model_name,
            messages=[
                {
                    "role": "system",
                    "content": "당신은 지정학 브리핑 작성 전문가입니다. 입력 데이터에 근거한 구조화된 문서를 작성합니다.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=4096,
        )
        return response.choices[0].message.content or ""

    async def generate(self, scenario_id: str) -> dict[str, Any]:
        pool = get_pool()
        async with pool.acquire() as conn:
            scenario = await conn.fetchrow(
                "SELECT id, name, region_name, region_bbox, question FROM scenarios WHERE id = $1",
                scenario_id,
            )
            if not scenario:
                raise ValueError("Scenario not found")

            seed_row = await conn.fetchrow(
                "SELECT text, created_at FROM seeds WHERE scenario_id = $1 ORDER BY created_at DESC LIMIT 1",
                scenario_id,
            )
            sim_row = await conn.fetchrow(
                """SELECT id, results, report
                   FROM simulation_results
                   WHERE scenario_id = $1 AND status = 'completed'
                   ORDER BY completed_at DESC NULLS LAST, created_at DESC
                   LIMIT 1""",
                scenario_id,
            )
            geopolitics_rows = await conn.fetch(
                """SELECT actor_id, action_type, content, round_number, event_at
                   FROM geopolitics_events
                   WHERE scenario_id = $1
                   ORDER BY round_number DESC, event_at DESC
                   LIMIT 500""",
                scenario_id,
            )
            version_row = await conn.fetchrow(
                "SELECT version FROM briefings WHERE scenario_id = $1 ORDER BY version DESC, created_at DESC LIMIT 1",
                scenario_id,
            )

        seed_text = seed_row["text"] if seed_row and seed_row["text"] else "시드 문서 없음"
        seed_created = seed_row["created_at"] if seed_row else None
        simulation_summary = self._summarize_simulation_actions(
            sim_row["results"] if sim_row else None,
        )
        geopolitics_summary = self._summarize_geopolitics_events(list(geopolitics_rows))
        report_text = (
            sim_row["report"]
            if sim_row and sim_row["report"]
            else "MiroFish 보고서 없음"
        )

        current_osint_section = ""
        try:
            bbox = json.loads(scenario["region_bbox"])
        except (json.JSONDecodeError, TypeError):
            bbox = []
        if bbox:
            osint_snapshot = await self._collect_current_osint(bbox)
            if osint_snapshot:
                seed_time_label = str(seed_created)[:19] if seed_created else "불명"
                current_osint_section = (
                    f"## 현재 OSINT 상황 (브리핑 생성 시점)\n"
                    f"아래는 브리핑 생성 시점의 실시간 OSINT 데이터입니다.\n"
                    f"시드 상황 분석은 시나리오 생성 시점({seed_time_label})의 데이터이므로, "
                    f"현재와 차이가 있을 수 있습니다.\n\n"
                    f"{osint_snapshot}"
                )

        prompt = BRIEFING_PROMPT.format(
            scenario_name=scenario["name"],
            region_name=scenario["region_name"],
            question=scenario["question"],
            seed_text=seed_text,
            simulation_summary=simulation_summary,
            geopolitics_summary=geopolitics_summary,
            report_text=report_text,
            current_osint_section=current_osint_section,
        )
        content = await self._call_llm(prompt)

        briefing_id = str(uuid.uuid4())
        version = (version_row["version"] if version_row else 0) + 1
        now = datetime.now(timezone.utc).isoformat()

        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO briefings (id, scenario_id, content, version, created_at, updated_at)
                   VALUES ($1, $2, $3, $4, $5, $6)""",
                briefing_id,
                scenario_id,
                content,
                version,
                now,
                now,
            )

        return {
            "id": briefing_id,
            "scenario_id": scenario_id,
            "content": content,
            "version": version,
            "created_at": now,
        }
