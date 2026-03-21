from __future__ import annotations

from typing import Any


def recommend_params(metadata: dict[str, Any]) -> dict[str, Any]:
    vessels = metadata.get("vessels_count", 0)
    tension = metadata.get("tension_score", 0.0)
    actors = metadata.get("actors_identified", [])
    flights = metadata.get("military_flights_count", 0)
    sats = metadata.get("satellites_count", 0)
    osint_sources = metadata.get("osint_sources_used", 0)

    actor_count = len(actors) if isinstance(actors, list) else 0
    mil_density = vessels + flights + sats

    options = [
        _build_quick(tension, actor_count, mil_density),
        _build_standard(tension, actor_count, mil_density),
        _build_deep(tension, actor_count, mil_density),
    ]

    if tension >= 0.7 or mil_density >= 15:
        recommended = "deep_analysis"
    elif tension >= 0.3 or mil_density >= 5:
        recommended = "standard"
    else:
        recommended = "quick_scan"

    return {"options": options, "recommended": recommended}


def _build_quick(tension: float, actor_count: int, mil_density: int) -> dict[str, Any]:
    return {
        "id": "quick_scan",
        "label": "빠른 탐색",
        "description": "소규모 시뮬레이션으로 핵심 행위자의 초기 반응을 빠르게 확인합니다.",
        "confidence": round(min(0.9, 0.7 + (1.0 - tension) * 0.2), 2),
        "reasoning": (
            f"행위자 {actor_count}명, 군사 밀도 {mil_density}. "
            "빠른 개요 파악에 적합합니다."
        ),
        "data": {
            "platform": "twitter",
            "max_rounds": min(5, max(3, actor_count)),
            "simulation_hours": 24,
            "geopolitics_enabled": False,
            "web_search_enabled": False,
        },
    }


def _build_standard(tension: float, actor_count: int, mil_density: int) -> dict[str, Any]:
    rounds = min(15, max(7, actor_count + int(tension * 5)))
    hours = 48 if tension >= 0.5 else 24

    return {
        "id": "standard",
        "label": "표준 분석",
        "description": "균형 잡힌 시뮬레이션으로 행위자 간 상호작용과 여론 전파를 분석합니다.",
        "confidence": 0.75,
        "reasoning": (
            f"긴장도 {tension:.1f}, 행위자 {actor_count}명, 군사 밀도 {mil_density}. "
            f"{rounds}라운드/{hours}시간이 상호작용 패턴 파악에 적합합니다."
        ),
        "data": {
            "platform": "twitter",
            "max_rounds": rounds,
            "simulation_hours": hours,
            "geopolitics_enabled": tension >= 0.4,
            "web_search_enabled": False,
        },
    }


def _build_deep(tension: float, actor_count: int, mil_density: int) -> dict[str, Any]:
    rounds = min(30, max(10, actor_count * 2 + int(tension * 10)))
    hours = 72 if tension >= 0.7 else 48

    return {
        "id": "deep_analysis",
        "label": "심층 분석",
        "description": "장기 시뮬레이션으로 지정학적 역학과 에스컬레이션 경로를 추적합니다.",
        "confidence": round(min(0.95, 0.5 + tension * 0.4 + min(mil_density, 20) * 0.01), 2),
        "reasoning": (
            f"긴장도 {tension:.1f}, 군사 자산 {mil_density}건 감지. "
            f"지정학 분석 활성화 + {rounds}라운드로 에스컬레이션 역학을 추적합니다."
        ),
        "data": {
            "platform": "twitter",
            "max_rounds": rounds,
            "simulation_hours": hours,
            "geopolitics_enabled": True,
            "web_search_enabled": True,
        },
    }
