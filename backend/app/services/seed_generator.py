"""시드 문서 생성 서비스.

ShadowBroker OSINT 데이터를 기반으로 MiroFish에 전달할
자연어 시드 문서(마크다운)를 생성한다.

흐름: SB API → 군함 식별/매핑 → GDELT 컨텍스트 → LLM 시드 문서 생성
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from openai import AsyncOpenAI

from app.clients.shadowbroker import BBox, ShadowBrokerClient
from app.config import settings
from app.database import get_pool
from app.services.gdelt_extractor import extract_gdelt_context, format_gdelt_text
from app.services.vessel_mapper import VesselMapper
from app.services.web_search import WebSearchService

logger = logging.getLogger(__name__)

SEED_GENERATION_PROMPT = """\
당신은 지정학적 분석가입니다. 아래 OSINT 데이터를 기반으로
시뮬레이션 시드 문서를 마크다운으로 작성해 주세요.

## 군함 배치 현황
{vessel_deployment}

## 군사 기지 배치
{military_bases}

## 군용 항공기 활동
{military_flights}

## 특별 추적 항공기 (VIP/정부 전용기)
{tracked_flights}

## 무인기(UAV) 활동
{uav_activity}

## 정찰/감시 위성 활동
{satellite_activity}

## GDELT 분쟁 이벤트 (최근)
{gdelt_context}

## 실시간 OSINT 정보
{osint_signals}

{recent_news_section}
{resolver_context_section}
## 시뮬레이션 질문
{user_question}

## 해역 정보
{region_name}

다음 형식으로 작성하세요:
1. **현재 상황 요약** (200자 이내) — 해역의 군사적 긴장 상황 개요
2. **주요 행위자와 그 입장** — 각 국가의 군사력 배치와 외교적 입장
3. **긴장 요인 및 잠재적 충돌 시나리오** — 구체적 대립 요인
4. **각 행위자의 예상 반응 경로** — 외교적/군사적 반응 시나리오

시드 문서는 약 2000자 이내로 작성하세요.
각 행위자(국가)는 이후 소셜미디어 시뮬레이션에서 개별 에이전트로 동작합니다.
실제 OSINT 데이터에 기반하여 현실적으로 작성하세요.
"""

PERSPECTIVE_CONFIGS: list[dict[str, str]] = [
    {
        "id": "military_focus",
        "label": "군사 긴장 중심",
        "instruction": (
            "군사적 관점에서 작성하세요. 군함 배치, 군사 훈련, 무기 체계, 군사 동맹에 초점을 맞추세요. "
            "군사적 충돌 가능성과 억지력 균형을 강조하세요."
        ),
    },
    {
        "id": "diplomatic_focus",
        "label": "외교 협상 중심",
        "instruction": (
            "외교적 관점에서 작성하세요. 다자간 협상, 국제기구 중재, 외교 성명, 경제 제재에 초점을 맞추세요. "
            "대화와 협상을 통한 긴장 완화 가능성을 강조하세요."
        ),
    },
    {
        "id": "neutral",
        "label": "균형 분석",
        "instruction": (
            "균형 잡힌 중립적 관점에서 작성하세요. 군사적 요소와 외교적 요소를 동등하게 다루세요. "
            "각 행위자의 입장을 공정하게 제시하고, 다양한 시나리오 가능성을 열어두세요."
        ),
    },
]


class SeedGenerator:
    def __init__(
        self,
        sb_client: ShadowBrokerClient,
        vessel_mapper: VesselMapper | None = None,
    ):
        self.sb = sb_client
        self.mapper = vessel_mapper or VesselMapper()
        self._llm = AsyncOpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )

    def _filter_by_bbox(
        self,
        items: list[dict],
        bbox: list[float],
        lng_key: str = "lng",
    ) -> list[dict]:
        if len(bbox) < 4:
            return items
        min_lng, min_lat, max_lng, max_lat = bbox
        result: list[dict] = []
        for item in items:
            lat = item.get("lat")
            lng = item.get(lng_key)
            if (
                lat is not None
                and lng is not None
                and min_lat <= lat <= max_lat
                and min_lng <= lng <= max_lng
            ):
                result.append(item)
        return result

    def _summarize_flights(self, flights: list[dict], bbox: list[float]) -> str:
        filtered = self._filter_by_bbox(flights, bbox)
        if not filtered:
            return ""
        uavs = [f for f in filtered if f.get("is_uav")]
        manned = [f for f in filtered if not f.get("is_uav")]

        by_country: dict[str, list[str]] = {}
        for flight in manned:
            country = flight.get("country", "불명")
            mtype = flight.get("military_type", flight.get("aircraft_type", "항공기"))
            by_country.setdefault(country, []).append(mtype)

        lines: list[str] = []
        for country, types in by_country.items():
            from collections import Counter

            counts = Counter(types)
            desc = ", ".join(f"{name} {count}대" for name, count in counts.most_common(5))
            lines.append(f"- {country}: {desc}")

        if uavs:
            uav_countries = set(u.get("country", "불명") for u in uavs)
            lines.append(f"- 무인기(UAV) {len(uavs)}대 감지 ({', '.join(uav_countries)})")

        return "\n".join(lines) if lines else ""

    def _summarize_military_bases(self, bases: list[dict], bbox: list[float]) -> str:
        filtered = self._filter_by_bbox(bases, bbox)
        if not filtered:
            return ""

        by_country: dict[str, list[str]] = {}
        for base in filtered:
            country = base.get("country", "불명")
            branch = base.get("branch", "기타")
            by_country.setdefault(country, []).append(branch)

        lines: list[str] = []
        for country, branches in by_country.items():
            branch_list = ", ".join(sorted(set(branches)))
            lines.append(f"- {country}: {len(branches)}개 기지 ({branch_list})")

        return "\n".join(lines) if lines else ""

    def _summarize_uavs(self, uavs: list[dict], bbox: list[float]) -> str:
        filtered = self._filter_by_bbox(uavs, bbox)
        if not filtered:
            return ""

        by_country: dict[str, list[dict]] = {}
        for uav in filtered:
            country = uav.get("country", "불명")
            by_country.setdefault(country, []).append(uav)

        lines: list[str] = []
        for country, country_uavs in by_country.items():
            from collections import Counter

            type_counts = Counter(u.get("uav_type", "UAV") for u in country_uavs)
            for uav_type, count in type_counts.most_common():
                models = sorted(
                    {
                        u.get("aircraft_model", "모델 불명")
                        for u in country_uavs
                        if u.get("uav_type", "UAV") == uav_type
                    },
                )
                model_text = ", ".join(models)
                lines.append(f"- {country}: {uav_type} {count}대 ({model_text})")

        return "\n".join(lines) if lines else ""

    def _summarize_tracked_flights(self, flights: list[dict], bbox: list[float]) -> str:
        filtered = self._filter_by_bbox(flights, bbox)
        if not filtered:
            return ""

        lines: list[str] = []
        seen: set[tuple[str, str]] = set()
        for flight in filtered:
            callsign = flight.get("callsign", "UNKNOWN")
            country = flight.get("country", "불명")
            item = (callsign, country)
            if item in seen:
                continue
            seen.add(item)
            lines.append(f"- {callsign} ({country})")

        return "\n".join(lines) if lines else ""

    def _summarize_private_jets(self, jets: list[dict], bbox: list[float]) -> str:
        filtered = self._filter_by_bbox(jets, bbox)
        if not filtered:
            return ""

        countries = [j.get("country") for j in filtered if j.get("country")]
        if not countries:
            return f"- 프라이빗 제트 {len(filtered)}대 감지"

        from collections import Counter

        counts = Counter(countries)
        country_text = ", ".join(f"{name} {count}대" for name, count in counts.most_common(5))
        return f"- 프라이빗 제트 {len(filtered)}대 감지 ({country_text})"

    def _summarize_kiwisdr(self, nodes: list[dict], bbox: list[float]) -> str:
        filtered = self._filter_by_bbox(nodes, bbox, lng_key="lon")
        if not filtered:
            return ""
        return f"- HF 수신기(KiwiSDR) {len(filtered)}개 감지 — SIGINT 가용"

    def _summarize_power_plants(self, plants: list[dict], bbox: list[float]) -> str:
        filtered = self._filter_by_bbox(plants, bbox)
        if not filtered:
            return ""

        from collections import Counter

        fuel_counts = Counter(p.get("fuel_type", "기타") for p in filtered)
        fuel_types = ", ".join(f"{fuel} {count}개" for fuel, count in fuel_counts.most_common())
        nuclear_count = sum(
            1
            for p in filtered
            if str(p.get("fuel_type", "")).strip().lower() in {"nuclear", "nuclear_power"}
        )
        nuclear_suffix = f", 원전 {nuclear_count}개" if nuclear_count else ""
        return f"- 발전소 {len(filtered)}개 ({fuel_types}{nuclear_suffix})"

    def _summarize_datacenters(self, dcs: list[dict], bbox: list[float]) -> str:
        filtered = self._filter_by_bbox(dcs, bbox)
        if not filtered:
            return ""

        companies = sorted({dc.get("company", "미상") for dc in filtered})
        company_text = ", ".join(companies[:8])
        if len(companies) > 8:
            company_text += ", ..."
        return f"- 데이터센터 {len(filtered)}개 ({company_text})"

    def _summarize_earthquakes(self, quakes: list[dict], bbox: list[float]) -> str:
        filtered = self._filter_by_bbox(quakes, bbox)
        strong = [q for q in filtered if q.get("mag", 0) >= 4.0]
        if not strong:
            return ""

        max_quake = max(strong, key=lambda q: q.get("mag", 0))
        max_mag = max_quake.get("mag", 0)
        place = max_quake.get("place", "위치 불명")
        return f"- 지진 {len(strong)}건 (최대 M{max_mag:.1f}, {place})"

    def _summarize_space_weather(self, sw: dict | None) -> str:
        if not isinstance(sw, dict):
            return ""
        kp_index = sw.get("kp_index")
        if not isinstance(kp_index, (int, float)) or kp_index < 5:
            return ""
        kp_text = sw.get("kp_text", "STORM")
        return f"- 우주 기상 경보: Kp={kp_index} ({kp_text}) — 위성·통신 교란 가능"

    def _summarize_satellites(self, satellites: list[dict], bbox: list[float]) -> str:
        filtered = self._filter_by_bbox(satellites, bbox)
        military_types = {"military_recon", "sar", "sigint", "early_warning"}
        mil_sats = [s for s in filtered if s.get("mission_type") in military_types]
        if not mil_sats:
            return ""

        by_country: dict[str, list[str]] = {}
        for sat in mil_sats:
            country = sat.get("country", "불명")
            mission = sat.get("mission_type", "정찰")
            by_country.setdefault(country, []).append(mission)

        lines: list[str] = []
        for country, missions in by_country.items():
            from collections import Counter

            counts = Counter(missions)
            desc = ", ".join(
                f"{mission} {count}기" for mission, count in counts.most_common()
            )
            lines.append(f"- {country}: {desc}")

        return "\n".join(lines) if lines else ""

    def _summarize_gps_jamming(self, jamming: list[dict], bbox: list[float]) -> str:
        filtered = self._filter_by_bbox(jamming, bbox)
        if not filtered:
            return ""
        max_severity = max(j.get("severity", 0) for j in filtered)
        total_affected = sum(j.get("affected_count", 0) for j in filtered)
        return (
            f"- GPS 교란 감지: {len(filtered)}개 구역, 최대 심각도 {max_severity}%, "
            f"영향 항공기 {total_affected}대"
        )

    def _summarize_news(self, news: list[dict], bbox: list[float]) -> str:
        filtered = self._filter_by_bbox(news, bbox)
        if not filtered:
            return ""
        filtered.sort(key=lambda n: n.get("risk_score", 0), reverse=True)
        lines: list[str] = []
        for item in filtered[:5]:
            title = item.get("title", "")
            source = item.get("source", "")
            if title:
                lines.append(f"- [{source}] {title}")
        return "\n".join(lines) if lines else ""

    def _summarize_liveuamap(self, events: list[dict], bbox: list[float]) -> str:
        filtered = self._filter_by_bbox(events, bbox)
        if not filtered:
            return ""
        lines: list[str] = []
        for event in filtered[:5]:
            title = event.get("title", "")
            if title:
                lines.append(f"- {title}")
        if lines:
            return f"실시간 분쟁 이벤트 {len(filtered)}건:\n" + "\n".join(lines)
        return ""

    def _summarize_outages(self, outages: list[dict], bbox: list[float]) -> str:
        filtered = self._filter_by_bbox(outages, bbox)
        if not filtered:
            return ""
        severe = [o for o in filtered if o.get("severity", 0) >= 50]
        if not severe:
            return ""
        countries = set(o.get("country_name", "불명") for o in severe)
        return f"- 심각한 인터넷 장애 {len(severe)}건 ({', '.join(countries)})"

    def _summarize_stocks(self, stocks: list) -> str:
        if not stocks:
            return ""
        lines: list[str] = []
        for stock in stocks:
            if not isinstance(stock, dict):
                continue
            symbol = stock.get("symbol", stock.get("name", ""))
            change = stock.get("change_percent", 0)
            if not isinstance(change, (int, float)):
                continue
            direction = "+" if change >= 0 else ""
            lines.append(f"{symbol} {direction}{change:.1f}%")
        return ("방산주/에너지: " + ", ".join(lines)) if lines else ""

    def _summarize_fires(self, fires: list[dict], bbox: list[float]) -> str:
        filtered = self._filter_by_bbox(fires, bbox)
        if not filtered:
            return ""
        high_frp = [f for f in filtered if f.get("frp", 0) >= 50]
        if not high_frp:
            return ""
        return f"- 대규모 열원 감지: {len(high_frp)}건 (FRP ≥ 50MW)"

    def _summarize_frontlines(self, frontlines: dict[str, Any], bbox: list[float]) -> str:
        features = frontlines.get("features", []) if isinstance(frontlines, dict) else []
        if not features or len(bbox) < 4:
            return ""
        min_lng, min_lat, max_lng, max_lat = bbox
        touched = 0
        for feature in features:
            geometry = feature.get("geometry", {})
            coords = geometry.get("coordinates", [])
            if geometry.get("type") == "LineString":
                line_points = coords
            elif geometry.get("type") == "MultiLineString":
                line_points = [p for line in coords for p in line]
            else:
                line_points = []
            if any(
                len(point) >= 2
                and min_lng <= point[0] <= max_lng
                and min_lat <= point[1] <= max_lat
                for point in line_points
            ):
                touched += 1
        if touched == 0:
            return ""
        return f"- 활성 전선 구간 {touched}개 감지"

    async def _collect_and_summarize(
        self,
        bbox: list[float],
        question: str,
        region_name: str = "",
        web_search_enabled: bool = False,
    ) -> dict[str, Any]:
        sb_bbox = BBox(s=bbox[1], w=bbox[0], n=bbox[3], e=bbox[2])

        fast_data = await self.sb.get_fast_data(sb_bbox)
        slow_data = await self.sb.get_slow_data(sb_bbox)

        ships = fast_data.get("ships", [])
        military_vessels = self.mapper.identify_military_vessels(ships)
        actors = self.mapper.map_to_actors(military_vessels)
        vessel_text = self.mapper.format_deployment_text(actors)

        gdelt_data = slow_data.get("gdelt", [])
        gdelt_context = extract_gdelt_context(gdelt_data, bbox)
        gdelt_text = format_gdelt_text(gdelt_context)

        mil_flights = fast_data.get("military_flights", [])
        flights_text = self._summarize_flights(mil_flights, bbox)

        military_bases = slow_data.get("military_bases", [])
        military_bases_text = self._summarize_military_bases(military_bases, bbox)

        tracked_flights = fast_data.get("tracked_flights", [])
        tracked_text = self._summarize_tracked_flights(tracked_flights, bbox)

        uavs = fast_data.get("uavs", [])
        uav_text = self._summarize_uavs(uavs, bbox)

        satellites = fast_data.get("satellites", [])
        satellite_text = self._summarize_satellites(satellites, bbox)

        gps_text = self._summarize_gps_jamming(fast_data.get("gps_jamming", []), bbox)
        news_text = self._summarize_news(slow_data.get("news", []), bbox)
        liveuamap_text = self._summarize_liveuamap(fast_data.get("liveuamap", []), bbox)
        outage_text = self._summarize_outages(slow_data.get("internet_outages", []), bbox)
        stocks_text = self._summarize_stocks(slow_data.get("stocks", []))
        fires_text = self._summarize_fires(slow_data.get("firms_fires", []), bbox)
        frontlines_text = self._summarize_frontlines(slow_data.get("frontlines", {}), bbox)
        private_jets_text = self._summarize_private_jets(fast_data.get("private_jets", []), bbox)
        kiwisdr_text = self._summarize_kiwisdr(slow_data.get("kiwisdr", []), bbox)
        power_plants_text = self._summarize_power_plants(slow_data.get("power_plants", []), bbox)
        datacenters_text = self._summarize_datacenters(slow_data.get("datacenters", []), bbox)
        earthquakes_text = self._summarize_earthquakes(slow_data.get("earthquakes", []), bbox)
        space_weather_text = self._summarize_space_weather(slow_data.get("space_weather"))

        osint_signals_parts = [
            s
            for s in [
                gps_text,
                news_text,
                liveuamap_text,
                outage_text,
                stocks_text,
                fires_text,
                frontlines_text,
                private_jets_text,
                kiwisdr_text,
                power_plants_text,
                datacenters_text,
                earthquakes_text,
                space_weather_text,
            ]
            if s
        ]
        osint_signals = (
            "\n".join(osint_signals_parts)
            if osint_signals_parts
            else "(추가 OSINT 신호 없음)"
        )

        resolver_context_section = ""
        resolved_entity_count = 0
        used_observation_ids: list[str] = []
        try:
            resolver_ctx = await self._get_resolver_context(bbox)
            if resolver_ctx["entities"]:
                lines = []
                for ent in resolver_ctx["entities"][:20]:
                    lines.append(f"- **{ent['name']}** ({ent['object_type']}) — 신뢰도 {ent['confidence']:.0%}")
                resolved_entity_count = len(resolver_ctx["entities"])
                used_observation_ids = resolver_ctx["observation_ids"]
                entity_section = "\n".join(lines)

                proximity_text = ""
                if resolver_ctx["proximity_pairs"]:
                    prox_lines = []
                    for pair in resolver_ctx["proximity_pairs"][:10]:
                        prox_lines.append(
                            f"- {pair['source_type']} ↔ {pair['target_type']}: {pair['distance_km']:.1f}km"
                        )
                    proximity_text = "\n## 근접 엔티티 관계 (10km 이내)\n" + "\n".join(prox_lines) + "\n"

                resolver_context_section = (
                    f"## 엔티티 해소 결과 (Entity Resolution)\n{entity_section}\n{proximity_text}"
                )
        except Exception:
            logger.warning("Resolver context enrichment failed, continuing without it")

        recent_news_section = ""
        web_search_count = 0
        if web_search_enabled:
            try:
                ws = WebSearchService()
                keywords = WebSearchService.extract_keywords(
                    question, region_name, list(actors.keys()),
                )
                news_results = ws.search_news(keywords)
                formatted = ws.format_for_seed(news_results)
                if formatted:
                    recent_news_section = f"## 최근 뉴스 (웹 검색)\n{formatted}\n"
                    web_search_count = len(news_results)
            except Exception:
                logger.warning("Web search enrichment failed, continuing without it")

        filtered_flights = self._filter_by_bbox(mil_flights, bbox)
        filtered_sats = self._filter_by_bbox(satellites, bbox)
        filtered_military_bases = self._filter_by_bbox(military_bases, bbox)
        filtered_tracked_flights = self._filter_by_bbox(tracked_flights, bbox)
        filtered_uavs = self._filter_by_bbox(uavs, bbox)
        filtered_private_jets = self._filter_by_bbox(fast_data.get("private_jets", []), bbox)
        filtered_kiwisdr = self._filter_by_bbox(slow_data.get("kiwisdr", []), bbox, lng_key="lon")
        filtered_power_plants = self._filter_by_bbox(slow_data.get("power_plants", []), bbox)
        filtered_datacenters = self._filter_by_bbox(slow_data.get("datacenters", []), bbox)
        filtered_earthquakes = self._filter_by_bbox(slow_data.get("earthquakes", []), bbox)
        filtered_quakes_m4 = [q for q in filtered_earthquakes if q.get("mag", 0) >= 4.0]
        storm_space_weather = self._summarize_space_weather(slow_data.get("space_weather"))

        return {
            "prompt_vars": {
                "vessel_deployment": vessel_text or "(해역 내 군함 미감지)",
                "military_bases": military_bases_text or "(해역 내 군사 기지 미감지)",
                "military_flights": flights_text or "(해역 내 군용 항공기 미감지)",
                "tracked_flights": tracked_text or "(해역 내 특별 추적 항공기 미감지)",
                "uav_activity": uav_text or "(해역 내 UAV 활동 미감지)",
                "satellite_activity": satellite_text or "(해역 상공 군사 위성 미감지)",
                "gdelt_context": gdelt_text,
                "osint_signals": osint_signals,
                "recent_news_section": recent_news_section,
                "resolver_context_section": resolver_context_section,
                "user_question": question,
                "region_name": region_name or "미지정",
            },
            "metadata": {
                "vessels_count": len(military_vessels),
                "actors_identified": list(actors.keys()),
                "military_bases_count": len(filtered_military_bases),
                "military_flights_count": len(filtered_flights),
                "tracked_flights_count": len(filtered_tracked_flights),
                "uavs_count": len(filtered_uavs),
                "satellites_count": len(filtered_sats),
                "gdelt_events_count": gdelt_context["event_count"],
                "tension_score": gdelt_context["tension_score"],
                "osint_sources_used": len([s for s in osint_signals_parts if s]),
                "private_jets_count": len(filtered_private_jets),
                "kiwisdr_count": len(filtered_kiwisdr),
                "power_plants_count": len(filtered_power_plants),
                "datacenters_count": len(filtered_datacenters),
                "earthquakes_m4_count": len(filtered_quakes_m4),
                "space_weather_storm": bool(storm_space_weather),
                "web_search_count": web_search_count,
                "resolved_entity_count": resolved_entity_count,
                "used_observation_ids": used_observation_ids,
                "data_timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

    async def generate(
        self,
        bbox: list[float],
        question: str,
        region_name: str = "",
        web_search_enabled: bool = False,
    ) -> dict[str, Any]:
        ctx = await self._collect_and_summarize(bbox, question, region_name, web_search_enabled)

        prompt = SEED_GENERATION_PROMPT.format(**ctx["prompt_vars"])
        seed_text = await self._call_llm(prompt)

        logger.info(
            "Seed generated: %d vessels, %d actors, %d flights, %d sats, tension=%.1f, +%d osint, +%d web",
            ctx["metadata"]["vessels_count"],
            len(ctx["metadata"]["actors_identified"]),
            ctx["metadata"]["military_flights_count"],
            ctx["metadata"]["satellites_count"],
            ctx["metadata"]["tension_score"],
            ctx["metadata"]["osint_sources_used"],
            ctx["metadata"]["web_search_count"],
        )

        return {"text": seed_text, "metadata": ctx["metadata"]}

    async def _get_resolver_context(self, bbox: list[float]) -> dict[str, Any]:
        pool = get_pool()
        async with pool.acquire() as conn:
            obs_rows = await conn.fetch(
                """SELECT id, source_type, source_id
                   FROM observations
                   WHERE ST_Intersects(geom, ST_MakeEnvelope($1, $2, $3, $4, 4326))
                   LIMIT 200""",
                bbox[0], bbox[1], bbox[2], bbox[3],
            )

            observation_ids = [row["id"] for row in obs_rows]
            if not observation_ids:
                return {"entities": [], "proximity_pairs": [], "observation_ids": []}

            placeholders = ", ".join(f"${i+1}" for i in range(len(observation_ids)))
            decision_rows = await conn.fetch(
                f"""SELECT rd.observation_id, rd.resolved_stix_id, rd.confidence, rd.decision_type,
                           so.object_type, so.stix_json
                    FROM resolution_decisions rd
                    JOIN stix_objects so ON so.stix_id = rd.resolved_stix_id
                    WHERE rd.observation_id IN ({placeholders})
                      AND rd.decision_type IN ('auto', 'manual_merge')
                      AND rd.confidence >= 0.7
                    ORDER BY rd.confidence DESC
                    LIMIT 20""",
                *observation_ids,
            )

            import json as _json
            entities = []
            for row in decision_rows:
                stix_data = _json.loads(row["stix_json"]) if row["stix_json"] else {}
                entities.append({
                    "name": stix_data.get("name", row["resolved_stix_id"]),
                    "object_type": row["object_type"],
                    "confidence": row["confidence"],
                    "stix_id": row["resolved_stix_id"],
                })

            prox_rows = await conn.fetch(
                """SELECT a.source_type as src_type, b.source_type as tgt_type,
                          ST_Distance(a.geom::geography, b.geom::geography) / 1000.0 as distance_km
                   FROM observations a, observations b
                   WHERE a.id < b.id
                     AND ST_DWithin(a.geom::geography, b.geom::geography, 10000)
                     AND ST_Intersects(a.geom, ST_MakeEnvelope($1, $2, $3, $4, 4326))
                   LIMIT 10""",
                bbox[0], bbox[1], bbox[2], bbox[3],
            )

            proximity_pairs = [
                {"source_type": r["src_type"], "target_type": r["tgt_type"], "distance_km": r["distance_km"]}
                for r in prox_rows
            ]

        return {
            "entities": entities,
            "proximity_pairs": proximity_pairs,
            "observation_ids": observation_ids,
        }

    async def _call_llm(self, prompt: str, temperature: float = 0.4) -> str:
        response = await self._llm.chat.completions.create(
            model=settings.llm_model_name,
            messages=[
                {
                    "role": "system",
                    "content": "당신은 지정학적 분석 전문가입니다. OSINT 데이터를 기반으로 정확하고 현실적인 분석 문서를 작성합니다.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
            max_tokens=2048,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        )
        return response.choices[0].message.content or ""

    async def generate_options(
        self,
        bbox: list[float],
        question: str,
        region_name: str = "",
        num_options: int = 3,
        web_search_enabled: bool = False,
    ) -> dict[str, Any]:
        ctx = await self._collect_and_summarize(bbox, question, region_name, web_search_enabled)
        perspectives = PERSPECTIVE_CONFIGS[:num_options]

        async def _gen_one(perspective: dict[str, str]) -> dict[str, Any]:
            prompt = SEED_GENERATION_PROMPT.format(**ctx["prompt_vars"])
            prompt += f"\n\n## 분석 관점 지시\n{perspective['instruction']}"
            text = await self._call_llm(prompt, temperature=0.6)
            return {
                "id": perspective["id"],
                "label": perspective["label"],
                "text": text,
            }

        results = await asyncio.gather(*[_gen_one(p) for p in perspectives])

        metadata = ctx["metadata"]
        tension = metadata.get("tension_score", 0.0)
        vessels = metadata.get("vessels_count", 0)

        options = []
        for result in results:
            if result["id"] == "military_focus":
                confidence = min(0.95, 0.6 + tension * 0.3 + min(vessels, 10) * 0.01)
                reasoning = (
                    f"GDELT 긴장도 {tension:.1f}, 군함 {vessels}척 감지. "
                    "군사 데이터가 풍부하여 군사 중심 분석이 높은 신뢰도를 가집니다."
                )
            elif result["id"] == "diplomatic_focus":
                confidence = min(0.95, 0.5 + (1.0 - tension) * 0.3)
                reasoning = (
                    f"GDELT 긴장도 {tension:.1f}. "
                    "외교적 관점은 긴장 완화 시나리오 탐색에 유용합니다."
                )
            else:
                confidence = 0.75
                reasoning = "균형 잡힌 분석으로 군사적·외교적 요소를 동등하게 고려합니다."

            options.append({
                "id": result["id"],
                "label": result["label"],
                "description": result["text"][:200] + "..." if len(result["text"]) > 200 else result["text"],
                "confidence": round(confidence, 2),
                "reasoning": reasoning,
                "data": {"seed_text": result["text"]},
            })

        recommended = max(options, key=lambda o: o["confidence"])["id"]

        logger.info(
            "Seed options generated: %d options, recommended=%s, tension=%.1f",
            len(options), recommended, tension,
        )

        return {
            "options": options,
            "recommended": recommended,
            "metadata": metadata,
        }
