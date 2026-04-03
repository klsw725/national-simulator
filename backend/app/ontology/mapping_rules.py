"""OSINT 소스 → 온톨로지 엔티티 매핑 규칙.

⚠️ 좌표 필드명 지뢰 (AGENTS.md):
   - ships/flights/satellites: ``lng``
   - CCTV/KiwiSDR: ``lon``
   통일하면 ShadowBroker 내부 뷰포트 필터링이 깨진다.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FieldMapping:
    target_field: str
    source_path: str


@dataclass(frozen=True)
class AutoEdge:
    edge_type: str
    target_entity_type: str
    resolve_by: str


@dataclass(frozen=True)
class MappingRule:
    source: str
    entity_type: str
    coord_lng_field: str
    field_mappings: list[FieldMapping] = field(default_factory=list)
    auto_edges: list[AutoEdge] = field(default_factory=list)


MAPPING_RULES: dict[str, MappingRule] = {}


def _register(rule: MappingRule) -> MappingRule:
    MAPPING_RULES[rule.source] = rule
    return rule


_register(MappingRule(
    source="shadowbroker.ships",
    entity_type="x-vessel",
    coord_lng_field="lng",
    field_mappings=[
        FieldMapping("name", "ship.name"),
        FieldMapping("mmsi", "ship.mmsi"),
        FieldMapping("flag_state", "ship.flag"),
        FieldMapping("vessel_type", "ship.ship_type"),
    ],
    auto_edges=[
        AutoEdge("DEPLOYED_TO", "x-strategic-region", "coordinates"),
        AutoEdge("COMMANDED_BY", "x-military-force", "flag_state+navy"),
    ],
))

_register(MappingRule(
    source="shadowbroker.military_flights",
    entity_type="x-aircraft",
    coord_lng_field="lng",
    field_mappings=[
        FieldMapping("icao24", "flight.icao24"),
        FieldMapping("aircraft_type", "flight.aircraft_type"),
        FieldMapping("country", "flight.country"),
    ],
    auto_edges=[
        AutoEdge("OPERATES_IN", "x-strategic-region", "coordinates"),
    ],
))

_register(MappingRule(
    source="shadowbroker.satellites",
    entity_type="x-satellite",
    coord_lng_field="lng",
    field_mappings=[
        FieldMapping("norad_id", "satellite.norad_id"),
        FieldMapping("name", "satellite.name"),
        FieldMapping("country", "satellite.country"),
        FieldMapping("mission_type", "satellite.mission_type"),
    ],
    auto_edges=[
        AutoEdge("OPERATES_IN", "x-strategic-region", "coordinates"),
    ],
))

_register(MappingRule(
    source="shadowbroker.cctv",
    entity_type="x-facility",
    coord_lng_field="lon",
    field_mappings=[
        FieldMapping("name", "cctv.name"),
        FieldMapping("country", "cctv.country"),
        FieldMapping("facility_type", "'surveillance'"),
    ],
    auto_edges=[
        AutoEdge("OBSERVED_AT", "x-strategic-region", "coordinates"),
    ],
))

_register(MappingRule(
    source="shadowbroker.kiwisdr",
    entity_type="x-facility",
    coord_lng_field="lon",
    field_mappings=[
        FieldMapping("name", "sdr.name"),
        FieldMapping("country", "sdr.country"),
        FieldMapping("facility_type", "'signals_intelligence'"),
    ],
    auto_edges=[
        AutoEdge("OBSERVED_AT", "x-strategic-region", "coordinates"),
    ],
))

_register(MappingRule(
    source="shadowbroker.gdelt",
    entity_type="auto_classify",
    coord_lng_field="lng",
    field_mappings=[
        FieldMapping("name", "event.headline"),
        FieldMapping("event_type", "event.event_code"),
        FieldMapping("source_url", "event.source_url"),
        FieldMapping("goldstein_scale", "event.goldstein_scale"),
    ],
    auto_edges=[
        AutoEdge("CAUSES", "auto", "llm_analysis"),
    ],
))

GDELT_EVENT_TYPE_MAP: dict[str, str] = {
    "military": "x-military-event",
    "economic": "x-economic-event",
    "diplomatic": "x-diplomatic-event",
}


def get_rule(source: str) -> MappingRule:
    if source not in MAPPING_RULES:
        raise KeyError(f"Unknown OSINT source: {source}")
    return MAPPING_RULES[source]


def resolve_gdelt_entity_type(classification: str) -> str:
    return GDELT_EVENT_TYPE_MAP.get(
        classification, "x-geopolitical-event",
    )
