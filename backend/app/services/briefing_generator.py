from __future__ import annotations

import json
import logging
import uuid
from collections import Counter, defaultdict
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

## 시드 상황 분석 (시나리오 생성 시점 OSINT)
{seed_text}

## 시뮬레이션 행동 분석
{simulation_summary}

## 지정학 이벤트 분석 (긴장도·인과관계 포함)
{geopolitics_summary}

## 긴장도 궤적
{tension_trajectory}

## MiroFish 분석 보고서
{report_text}

{current_osint_section}
다음 구조를 정확히 따라 작성하세요:

# 상황 브리핑: [시나리오명]

## 1. 상황 요약 (200자 이내)
핵심 긴장 요인을 1문단으로 요약합니다. 반드시 구체적 수치(행위자 수, 액션 건수, 최대 긴장도)를 포함하세요.

## 2. 핵심 발견 (3~5개)
각 발견은 "**[발견 제목]**: [설명]" 형식으로 작성합니다.
반드시 시뮬레이션 데이터의 구체적 숫자나 행위자 이름을 인용하세요.
데이터가 없는 발견은 작성하지 마세요.

## 3. 행위자별 분석
각 행위자에 대해:
- 행동 건수와 유형 분포 (예: "미국: 공식 성명 12건, 동맹 지지 5건")
- 주요 대상 행위자 (누구에게 반응했는가)
- 긴장도 기여도 (해당 행위자의 행동이 긴장을 높였는가/낮췄는가)
- 대표 행동 1~2건 원문 인용

## 4. 시뮬레이션 라운드별 진행
라운드별로 핵심 사건을 시간순으로 서술합니다.
"라운드 N: [핵심 사건] (긴장도 X.XX)" 형식을 사용하세요.
에스컬레이션/디에스컬레이션 전환점을 명시하세요.

## 5. 지정학적 함의
시뮬레이션 결과에서 도출되는 전략적 시사점을 작성합니다.
추측이 아닌 시뮬레이션 데이터에서 관찰된 패턴만 기술하세요.

## 6. 권장 조치
정책 결정자에게 권고할 구체적 행동을 제안합니다.

{extra_sections}
## 부록: 데이터 소스 및 신뢰도
- 시뮬레이션 액션 N건, 지정학 이벤트 N건 (구체적 숫자 기입)
- 사용된 데이터 소스 나열
- 시뮬레이션 한계점 명시 (예: "소셜미디어 메타포 기반이므로 실제 군사작전과 1:1 대응하지 않음")

필수 규칙:
- 모든 주장에 입력 데이터의 구체적 수치·행위자명·라운드 번호를 인용하세요.
- 데이터가 없는 섹션은 "해당 데이터 없음"으로 명시하고, 추측으로 채우지 마세요.
- 같은 인용문을 여러 섹션에서 반복하지 마세요.
- 각 섹션은 고유한 분석 관점을 제공해야 합니다.
"""


class BriefingGenerator:
    def __init__(self, sb_client: ShadowBrokerClient | None = None):
        self._sb = sb_client
        self._llm = AsyncOpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )

    def _parse_actions(self, results_raw: str | None) -> list[dict[str, Any]]:
        if not results_raw:
            return []
        try:
            parsed = json.loads(results_raw)
        except json.JSONDecodeError:
            return []
        if isinstance(parsed, dict) and isinstance(parsed.get("actions"), list):
            return [a for a in parsed["actions"] if isinstance(a, dict)]
        if isinstance(parsed, list):
            return [a for a in parsed if isinstance(a, dict)]
        return []

    def _summarize_simulation_actions(self, results_raw: str | None) -> str:
        actions = self._parse_actions(results_raw)
        if not actions:
            return "시뮬레이션 액션 데이터 없음"

        actor_counter: Counter[str] = Counter()
        geo_label_counter: Counter[str] = Counter()
        round_actions: dict[int, list[dict]] = defaultdict(list)
        interaction_pairs: Counter[str] = Counter()

        for action in actions:
            actor = action.get("agent_name") or action.get("actor_id") or "unknown"
            actor_counter[str(actor)] += 1

            geo_label = action.get("geopolitics_label") or action.get("action_type") or "unknown"
            geo_label_counter[str(geo_label)] += 1

            rnd = action.get("round", 0)
            round_actions[rnd].append(action)

            target = action.get("target") or action.get("quoted_agent") or ""
            if target and str(target) != str(actor):
                interaction_pairs[f"{actor} → {target}"] += 1

        lines = [
            f"총 {len(actions)}건의 시뮬레이션 액션이 {len(round_actions)}개 라운드에 걸쳐 실행됨.",
            "",
            "### 행위자별 활동량",
        ]
        for actor, count in actor_counter.most_common():
            actor_actions = [a for a in actions if (a.get("agent_name") or a.get("actor_id")) == actor]
            actor_types = Counter(
                a.get("geopolitics_label") or a.get("action_type") or "unknown"
                for a in actor_actions
            )
            type_desc = ", ".join(f"{t} {c}건" for t, c in actor_types.most_common(3))
            lines.append(f"- **{actor}**: {count}건 ({type_desc})")

        lines.append("")
        lines.append("### 행동 유형 분포")
        for label, count in geo_label_counter.most_common():
            pct = count / len(actions) * 100
            lines.append(f"- {label}: {count}건 ({pct:.0f}%)")

        if interaction_pairs:
            lines.append("")
            lines.append("### 행위자 간 상호작용 (인용·리포스트·반응)")
            for pair, count in interaction_pairs.most_common(10):
                lines.append(f"- {pair}: {count}건")

        lines.append("")
        lines.append("### 라운드별 핵심 행동")
        for rnd in sorted(round_actions.keys()):
            rnd_acts = round_actions[rnd]
            rnd_types = Counter(
                a.get("geopolitics_label") or a.get("action_type") or ""
                for a in rnd_acts
            )
            dominant = rnd_types.most_common(1)[0][0] if rnd_types else "N/A"
            lines.append(f"- 라운드 {rnd}: {len(rnd_acts)}건 (주요: {dominant})")

            top_action = max(
                rnd_acts,
                key=lambda a: len(a.get("content") or a.get("post_content") or ""),
                default=None,
            )
            if top_action:
                actor = top_action.get("agent_name") or top_action.get("actor_id") or "?"
                content = (
                    top_action.get("content")
                    or top_action.get("post_content")
                    or top_action.get("text")
                    or ""
                )
                if content:
                    lines.append(f"  > [{actor}] {content[:300]}")

        return "\n".join(lines)

    def _summarize_geopolitics_events(self, rows: list[Any]) -> str:
        if not rows:
            return "지정학 이벤트 데이터 없음"

        round_data: dict[int, list[dict]] = defaultdict(list)
        actor_targets: dict[str, Counter] = defaultdict(Counter)
        magnitude_sum = 0.0
        magnitude_count = 0

        for row in rows:
            rnd = row.get("round_number") or 0
            round_data[rnd].append(row)

            actor = row.get("actor_id") or "unknown"
            targets_raw = row.get("target_actor_ids")
            if targets_raw:
                try:
                    targets = json.loads(targets_raw) if isinstance(targets_raw, str) else targets_raw
                except (json.JSONDecodeError, TypeError):
                    targets = []
                for t in (targets if isinstance(targets, list) else []):
                    actor_targets[str(actor)][str(t)] += 1

            mag = row.get("magnitude")
            if mag is not None:
                magnitude_sum += float(mag)
                magnitude_count += 1

        avg_magnitude = magnitude_sum / magnitude_count if magnitude_count else 0.0

        lines = [
            f"총 {len(rows)}건의 지정학 이벤트, 평균 긴장도(magnitude): {avg_magnitude:.2f}",
            "",
            "### 라운드별 긴장도 추이",
        ]
        for rnd in sorted(round_data.keys()):
            events = round_data[rnd]
            mags = [float(e.get("magnitude") or 0) for e in events]
            avg_mag = sum(mags) / len(mags) if mags else 0
            types = Counter(e.get("action_type") or "" for e in events)
            dominant = types.most_common(1)[0][0] if types else "N/A"
            lines.append(
                f"- 라운드 {rnd}: {len(events)}건, 평균 긴장도 {avg_mag:.2f}, 주요 유형: {dominant}"
            )

        if actor_targets:
            lines.append("")
            lines.append("### 행위자 → 대상 관계")
            for actor, targets in sorted(actor_targets.items()):
                target_desc = ", ".join(f"{t}({c}건)" for t, c in targets.most_common(5))
                lines.append(f"- **{actor}** → {target_desc}")

        peak_events = sorted(rows, key=lambda r: float(r.get("magnitude") or 0), reverse=True)[:5]
        if peak_events and any(e.get("magnitude") for e in peak_events):
            lines.append("")
            lines.append("### 최고 긴장도 이벤트 (상위 5건)")
            for evt in peak_events:
                mag = float(evt.get("magnitude") or 0)
                if mag == 0:
                    continue
                actor = evt.get("actor_id") or "?"
                rnd = evt.get("round_number") or "?"
                atype = evt.get("action_type") or "?"
                content = (evt.get("content") or "")[:200]
                lines.append(f"- [라운드 {rnd}] {actor}: {atype} (긴장도 {mag:.2f}) — {content}")

        return "\n".join(lines)

    async def _build_tension_trajectory(self, scenario_id: str) -> str:
        pool = get_pool()
        async with pool.acquire() as conn:
            round_rows = await conn.fetch(
                """SELECT round_number, COUNT(*) as cnt,
                          AVG(magnitude) as avg_mag,
                          MAX(magnitude) as max_mag
                   FROM geopolitics_events
                   WHERE scenario_id = $1 AND magnitude IS NOT NULL
                   GROUP BY round_number
                   ORDER BY round_number""",
                scenario_id,
            )
            dp_rows = await conn.fetch(
                """SELECT type, options, status, created_at
                   FROM decision_points
                   WHERE scenario_id = $1
                   ORDER BY created_at""",
                scenario_id,
            )

        if not round_rows:
            return "긴장도 데이터 없음 (지정학 이벤트에 magnitude 미포함)"

        lines = ["라운드별 긴장도 변화:"]
        peak_round = 0
        peak_mag = 0.0
        for row in round_rows:
            rnd = row["round_number"]
            avg = float(row["avg_mag"] or 0)
            mx = float(row["max_mag"] or 0)
            cnt = row["cnt"]
            bar = "█" * int(avg * 20)
            lines.append(f"  라운드 {rnd:>2}: {bar} {avg:.2f} (최대 {mx:.2f}, {cnt}건)")
            if mx > peak_mag:
                peak_mag = mx
                peak_round = rnd

        if peak_mag > 0:
            lines.append(f"\n최대 긴장 지점: 라운드 {peak_round} (긴장도 {peak_mag:.2f})")

        if dp_rows:
            lines.append(f"\nAI 개입 제안 발생: {len(dp_rows)}건")
            for dp in dp_rows:
                lines.append(f"  - 유형: {dp['type']}, 상태: {dp['status']}")

        return "\n".join(lines)

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

            ship_countries = Counter(s.get("country", "불명") for s in ships)
            flight_countries = Counter(f.get("country", "불명") for f in mil_flights)

            lines = [
                f"- 군함: {len(ships)}척",
            ]
            if ship_countries:
                lines.append(f"  국가별: {', '.join(f'{c} {n}척' for c, n in ship_countries.most_common(5))}")
            lines.append(f"- 군용기: {len(mil_flights)}대")
            if flight_countries:
                lines.append(f"  국가별: {', '.join(f'{c} {n}대' for c, n in flight_countries.most_common(5))}")
            lines.extend([
                f"- UAV: {len(uavs)}대",
                f"- 정찰위성: {len(satellites)}기",
                f"- 군사기지: {len(bases)}개",
            ])
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

    async def _call_llm(self, prompt: str) -> str:
        response = await self._llm.chat.completions.create(
            model=settings.llm_model_name,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "당신은 지정학 브리핑 작성 전문가입니다. "
                        "입력 데이터에 근거한 정량적·구조화된 문서를 작성합니다. "
                        "모든 주장에 구체적 숫자와 행위자명을 인용하세요. "
                        "데이터가 없는 내용은 추측하지 말고 '데이터 없음'으로 표기하세요."
                    ),
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
                """SELECT actor_id, action_type, content, round_number,
                          magnitude, target_actor_ids, event_at
                   FROM geopolitics_events
                   WHERE scenario_id = $1
                   ORDER BY round_number, event_at
                   LIMIT 1000""",
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
        geopolitics_summary = self._summarize_geopolitics_events(
            [dict(r) for r in geopolitics_rows],
        )
        report_text = (
            sim_row["report"]
            if sim_row and sim_row["report"]
            else "MiroFish 보고서 없음"
        )

        tension_trajectory = await self._build_tension_trajectory(scenario_id)

        current_osint_section = ""
        extra_sections = ""
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
                extra_sections = (
                    "## 7. 현재 상황 대비 변화 (시드 생성 이후)\n"
                    "시드 생성 시점과 현재 OSINT 데이터를 비교하여 주요 변화를 기술하세요.\n"
                    "현재 OSINT 데이터가 없는 경우 '데이터 없음'으로 표기하세요.\n"
                )

        prompt = BRIEFING_PROMPT.format(
            scenario_name=scenario["name"],
            region_name=scenario["region_name"],
            question=scenario["question"],
            seed_text=seed_text,
            simulation_summary=simulation_summary,
            geopolitics_summary=geopolitics_summary,
            tension_trajectory=tension_trajectory,
            report_text=report_text,
            current_osint_section=current_osint_section,
            extra_sections=extra_sections,
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
