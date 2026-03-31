"""GDELT 분쟁 컨텍스트 추출기.

ShadowBroker의 GDELT GeoJSON 데이터에서 bbox 내 이벤트를 필터링하고
긴장도 컨텍스트를 추출한다.

참고: SB의 GDELT 데이터는 위치별로 집계되어 제공되며,
개별 이벤트의 Goldstein Scale은 포함되지 않는다.
이벤트 밀도(count) 기반으로 긴장도를 추정한다.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def extract_gdelt_context(
    gdelt_features: list[dict[str, Any]],
    bbox: list[float],
) -> dict[str, Any]:
    """bbox 내의 GDELT 이벤트를 필터링하고 긴장도 컨텍스트 추출.

    Args:
        gdelt_features: SB /api/live-data/slow의 gdelt 필드 (GeoJSON Feature 배열)
        bbox: [min_lng, min_lat, max_lng, max_lat]

    Returns:
        {
            "event_count": int,       — 필터링된 총 이벤트 수
            "location_count": int,    — 분쟁 발생 위치 수
            "tension_score": float,   — 긴장도 추정 (0.0-10.0)
            "headlines": list[str],   — 주요 헤드라인 (최대 10개)
            "locations": list[str],   — 분쟁 발생 위치 이름 (최대 5개)
        }
    """
    if len(bbox) < 4:
        return _empty_context()

    min_lng, min_lat, max_lng, max_lat = bbox[0], bbox[1], bbox[2], bbox[3]

    filtered: list[dict[str, Any]] = []
    for feature in gdelt_features:
        coords = feature.get("geometry", {}).get("coordinates", [])
        if len(coords) < 2:
            continue
        lng, lat = coords[0], coords[1]
        if min_lat <= lat <= max_lat and min_lng <= lng <= max_lng:
            filtered.append(feature)

    if not filtered:
        return _empty_context()

    # 총 이벤트 수 (각 위치에 집계된 count 합산)
    total_events = sum(
        f.get("properties", {}).get("count", 1) for f in filtered
    )

    # 헤드라인 수집 (위치당 최대 3개)
    headlines: list[str] = []
    for f in filtered:
        props = f.get("properties", {})
        hl = props.get("_headlines_list", [])
        for h in hl[:3]:
            if h and h not in headlines:
                headlines.append(h)

    # 위치 이름 수집
    locations: list[str] = []
    for f in filtered:
        name = f.get("properties", {}).get("name", "")
        if name and name not in locations:
            locations.append(name)

    # 긴장도 추정: 이벤트 밀도 기반 (0-10 스케일)
    # 5개 이벤트 = 1점, 50개 이상 = 10점 (로그 스케일 근사)
    tension = min(10.0, total_events / 5.0)

    result = {
        "event_count": total_events,
        "location_count": len(filtered),
        "tension_score": round(tension, 1),
        "headlines": headlines[:10],
        "locations": locations[:5],
    }

    logger.info(
        "GDELT context: %d events at %d locations, tension=%.1f",
        total_events,
        len(filtered),
        tension,
    )
    return result


def format_gdelt_text(context: dict[str, Any]) -> str:
    """GDELT 컨텍스트를 LLM 프롬프트용 텍스트로 포맷."""
    if context["event_count"] == 0:
        return "(관심 지역 인근에서 감지된 GDELT 분쟁 이벤트 없음)"

    lines: list[str] = []
    lines.append(
        f"- 분쟁 이벤트: {context['event_count']}건 "
        f"({context['location_count']}개 지역)"
    )
    lines.append(f"- 긴장도 추정: {context['tension_score']}/10.0")

    if context["locations"]:
        lines.append(f"- 주요 지역: {', '.join(context['locations'])}")

    if context["headlines"]:
        lines.append("- 주요 뉴스:")
        for h in context["headlines"][:5]:
            lines.append(f"  - {h}")

    return "\n".join(lines)


def _empty_context() -> dict[str, Any]:
    return {
        "event_count": 0,
        "location_count": 0,
        "tension_score": 0.0,
        "headlines": [],
        "locations": [],
    }
