"""군함 식별 및 국가 행위자 매핑 서비스.

AIS 선박 데이터에서 군함을 식별하고 국가별 전력으로 그룹핑한다.

식별 전략 (우선순위):
1. ShadowBroker의 type 필드 기반 필터 (military_vessel, carrier)
2. military_vessels.json MMSI 매칭으로 enrichment (hull_number, class 등)
3. 선명 패턴 매칭 (USS, HMS, PLAN 등) — fallback
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# SB가 군함으로 분류하는 type 값
MILITARY_TYPES = {"military_vessel", "carrier"}

# 선명 접두사로 해군 소속 추정 (SB 분류 보완용)
NAME_PREFIXES: dict[str, str] = {
    "USS ": "US",
    "USNS ": "US",
    "HMS ": "UK",
    "HMAS ": "AU",
    "HMCS ": "CA",
    "JS ": "JP",
    "ROKS ": "KR",
    "FS ": "FR",
    "INS ": "IN",
    "KRI ": "ID",
}


class VesselMapper:
    def __init__(self, vessel_db_path: str | Path | None = None):
        if vessel_db_path is None:
            vessel_db_path = Path(__file__).parent.parent / "data" / "military_vessels.json"
        self._db = self._load_db(Path(vessel_db_path))
        self._mmsi_index: dict[str, dict] = {
            v["mmsi"]: v for v in self._db if v.get("mmsi")
        }

    @staticmethod
    def _load_db(path: Path) -> list[dict]:
        if not path.exists():
            logger.warning("Military vessels DB not found: %s", path)
            return []
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def identify_military_vessels(
        self, ships: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """AIS 선박 목록에서 군함만 필터링하고 DB 정보로 enrichment."""
        results: list[dict[str, Any]] = []
        for ship in ships:
            ship_type = ship.get("type", "")
            if ship_type not in MILITARY_TYPES:
                continue

            enriched: dict[str, Any] = {
                "mmsi": ship.get("mmsi"),
                "name": ship.get("name", "UNKNOWN"),
                "lat": ship.get("lat"),
                "lng": ship.get("lng"),
                "country": ship.get("country", "Unknown"),
                "vessel_type": ship_type,
            }

            # DB enrichment by MMSI
            mmsi_str = str(ship.get("mmsi", ""))
            db_entry = self._mmsi_index.get(mmsi_str)
            if db_entry:
                enriched["hull_number"] = db_entry.get("hull_number", "")
                enriched["vessel_class"] = db_entry.get("class", "")
                enriched["vessel_type"] = db_entry.get("type", ship_type)
                enriched["navy"] = db_entry.get("navy", "")
            else:
                # 선명 패턴 매칭으로 국가 보완
                name_upper = enriched["name"].upper()
                for prefix, country_code in NAME_PREFIXES.items():
                    if name_upper.startswith(prefix):
                        if enriched["country"] == "Unknown":
                            enriched["country"] = country_code
                        break

            results.append(enriched)

        logger.info("Identified %d military vessels from %d ships", len(results), len(ships))
        return results

    def map_to_actors(
        self, vessels: list[dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        """군함을 국가별 전력으로 그룹핑.

        반환 예:
        {
            "United States": {
                "vessels": [...],
                "force_summary": {"carrier": 1, "destroyer": 2}
            }
        }
        """
        actors: dict[str, dict[str, Any]] = {}
        for v in vessels:
            country = v.get("country", "Unknown")
            if country not in actors:
                actors[country] = {"vessels": [], "force_summary": {}}

            actors[country]["vessels"].append(v)
            vtype = v.get("vessel_type", "unknown")
            actors[country]["force_summary"][vtype] = (
                actors[country]["force_summary"].get(vtype, 0) + 1
            )

        return actors

    def format_deployment_text(
        self, actors: dict[str, dict[str, Any]]
    ) -> str:
        """국가별 군함 배치 현황을 텍스트로 포맷 (LLM 프롬프트용)."""
        lines: list[str] = []
        for country, data in sorted(actors.items()):
            summary_parts: list[str] = []
            for vtype, count in sorted(data["force_summary"].items()):
                summary_parts.append(f"{vtype} {count}척")
            lines.append(f"- **{country}**: {', '.join(summary_parts)}")

            for v in data["vessels"]:
                name = v.get("name", "UNKNOWN")
                hull = v.get("hull_number", "")
                vclass = v.get("vessel_class", "")
                lat = v.get("lat", "?")
                lng = v.get("lng", "?")
                detail = f"  - {name}"
                if hull:
                    detail += f" ({hull})"
                if vclass:
                    detail += f" [{vclass}]"
                detail += f" — 위치: {lat}, {lng}"
                lines.append(detail)

        return "\n".join(lines) if lines else "(해당 해역에서 감지된 군함 없음)"
