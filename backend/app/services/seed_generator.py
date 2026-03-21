"""시드 문서 생성 서비스.

ShadowBroker OSINT 데이터를 기반으로 MiroFish에 전달할
자연어 시드 문서(마크다운)를 생성한다.

흐름: SB API → 군함 식별/매핑 → GDELT 컨텍스트 → LLM 시드 문서 생성
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from openai import AsyncOpenAI

from app.clients.shadowbroker import BBox, ShadowBrokerClient
from app.config import settings
from app.services.gdelt_extractor import extract_gdelt_context, format_gdelt_text
from app.services.vessel_mapper import VesselMapper
from app.services.web_search import WebSearchService

logger = logging.getLogger(__name__)

SEED_GENERATION_PROMPT = """\
당신은 지정학적 분석가입니다. 아래 OSINT 데이터를 기반으로
시뮬레이션 시드 문서를 마크다운으로 작성해 주세요.

## 군함 배치 현황
{vessel_deployment}

## 군용 항공기 활동
{military_flights}

## 정찰/감시 위성 활동
{satellite_activity}

## GDELT 분쟁 이벤트 (최근)
{gdelt_context}

## 실시간 OSINT 정보
{osint_signals}

{recent_news_section}
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

    async def generate(
        self,
        bbox: list[float],
        question: str,
        region_name: str = "",
        web_search_enabled: bool = False,
    ) -> dict[str, Any]:
        """시드 문서 생성.

        Args:
            bbox: [min_lng, min_lat, max_lng, max_lat]
            question: 사용자의 시뮬레이션 질문
            region_name: 해역 이름 (예: "South China Sea")

        Returns:
            {"text": str, "metadata": dict}
        """
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

        satellites = fast_data.get("satellites", [])
        satellite_text = self._summarize_satellites(satellites, bbox)

        gps_text = self._summarize_gps_jamming(fast_data.get("gps_jamming", []), bbox)
        news_text = self._summarize_news(slow_data.get("news", []), bbox)
        liveuamap_text = self._summarize_liveuamap(fast_data.get("liveuamap", []), bbox)
        outage_text = self._summarize_outages(slow_data.get("internet_outages", []), bbox)
        stocks_text = self._summarize_stocks(slow_data.get("stocks", []))
        fires_text = self._summarize_fires(slow_data.get("firms_fires", []), bbox)
        frontlines_text = self._summarize_frontlines(slow_data.get("frontlines", {}), bbox)

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
            ]
            if s
        ]
        osint_signals = (
            "\n".join(osint_signals_parts)
            if osint_signals_parts
            else "(추가 OSINT 신호 없음)"
        )

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

        prompt = SEED_GENERATION_PROMPT.format(
            vessel_deployment=vessel_text or "(해역 내 군함 미감지)",
            military_flights=flights_text or "(해역 내 군용 항공기 미감지)",
            satellite_activity=satellite_text or "(해역 상공 군사 위성 미감지)",
            gdelt_context=gdelt_text,
            osint_signals=osint_signals,
            recent_news_section=recent_news_section,
            user_question=question,
            region_name=region_name or "미지정",
        )

        seed_text = await self._call_llm(prompt)

        filtered_flights = self._filter_by_bbox(mil_flights, bbox)
        filtered_sats = self._filter_by_bbox(satellites, bbox)

        metadata = {
            "vessels_count": len(military_vessels),
            "actors_identified": list(actors.keys()),
            "military_flights_count": len(filtered_flights),
            "satellites_count": len(filtered_sats),
            "gdelt_events_count": gdelt_context["event_count"],
            "tension_score": gdelt_context["tension_score"],
            "osint_sources_used": len([s for s in osint_signals_parts if s]),
            "web_search_count": web_search_count,
            "data_timestamp": datetime.now(timezone.utc).isoformat(),
        }

        logger.info(
            "Seed generated: %d vessels, %d actors, %d flights, %d sats, tension=%.1f, +%d osint, +%d web",
            metadata["vessels_count"],
            len(metadata["actors_identified"]),
            metadata["military_flights_count"],
            metadata["satellites_count"],
            metadata["tension_score"],
            metadata["osint_sources_used"],
            metadata["web_search_count"],
        )

        return {"text": seed_text, "metadata": metadata}

    async def _call_llm(self, prompt: str) -> str:
        """OpenAI Compatible API로 시드 문서 생성."""
        response = await self._llm.chat.completions.create(
            model=settings.llm_model_name,
            messages=[
                {
                    "role": "system",
                    "content": "당신은 지정학적 분석 전문가입니다. OSINT 데이터를 기반으로 정확하고 현실적인 분석 문서를 작성합니다.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
            max_tokens=2048,
        )
        return response.choices[0].message.content or ""
