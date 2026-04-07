from __future__ import annotations

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


async def fetch_latest_osint(region_bbox: list[float] | None = None) -> dict:
    try:
        params: dict[str, float] = {}
        if region_bbox and len(region_bbox) >= 4:
            params = {"w": region_bbox[0], "s": region_bbox[1], "e": region_bbox[2], "n": region_bbox[3]}

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{settings.shadowbroker_url}/api/live-data/fast",
                params=params or None,
            )
            resp.raise_for_status()
            fast_data = resp.json()

            resp_slow = await client.get(
                f"{settings.shadowbroker_url}/api/live-data/slow",
                params=params or None,
            )
            resp_slow.raise_for_status()
            slow_data = resp_slow.json()

        ships = fast_data.get("ships", [])
        flights = fast_data.get("flights", [])
        satellites = fast_data.get("satellites", [])
        gdelt = slow_data.get("gdelt", [])

        military_ships = [s for s in ships if s.get("navy") or s.get("ship_type", "").lower() in ("warship", "military")]
        military_flights = [f for f in flights if f.get("military_type")]

        return {
            "military_ships": military_ships[:20],
            "military_flights": military_flights[:20],
            "satellites": satellites[:10],
            "gdelt_events": gdelt[:20],
            "summary": (
                f"함정 {len(military_ships)}척, "
                f"군용기 {len(military_flights)}대, "
                f"위성 {len(satellites)}기 관측, "
                f"GDELT 이벤트 {len(gdelt)}건"
            ),
        }
    except Exception:
        logger.exception("Failed to fetch OSINT data from ShadowBroker")
        return {"military_ships": [], "military_flights": [], "satellites": [], "gdelt_events": [], "summary": "OSINT 데이터 수집 실패"}


def format_osint_for_prompt(osint: dict) -> str:
    lines = [f"[OSINT 관측 요약] {osint.get('summary', '')}"]

    for ship in osint.get("military_ships", [])[:5]:
        lines.append(f"- 함정: {ship.get('name', '?')} ({ship.get('flag', '?')}) 위치 {ship.get('lat', '?')},{ship.get('lng', '?')}")

    for flight in osint.get("military_flights", [])[:5]:
        lines.append(f"- 군용기: {flight.get('callsign', '?')} ({flight.get('country', '?')}) {flight.get('aircraft_type', '?')}")

    for evt in osint.get("gdelt_events", [])[:5]:
        lines.append(f"- GDELT: {evt.get('headline', evt.get('title', '?'))}")

    return "\n".join(lines)
