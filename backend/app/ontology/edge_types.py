from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class EdgeCategory(str, Enum):
    POLITICAL = "political"
    MILITARY = "military"
    ECONOMIC = "economic"
    CAUSAL = "causal"


class EdgeDirection(str, Enum):
    UNIDIRECTIONAL = "unidirectional"
    BIDIRECTIONAL = "bidirectional"
    N_TO_M = "n_to_m"
    TERNARY = "ternary"


@dataclass(frozen=True)
class EdgeTypeSpec:
    name: str
    category: EdgeCategory
    direction: EdgeDirection
    temporal_properties: list[str] = field(default_factory=list)
    strength_property: str | None = None
    description: str = ""


EDGE_TYPES: dict[str, EdgeTypeSpec] = {}


def _register(spec: EdgeTypeSpec) -> EdgeTypeSpec:
    EDGE_TYPES[spec.name] = spec
    return spec


ALLIED_WITH = _register(EdgeTypeSpec(
    name="ALLIED_WITH",
    category=EdgeCategory.POLITICAL,
    direction=EdgeDirection.BIDIRECTIONAL,
    temporal_properties=["since", "treaty_name"],
    strength_property="strength",
))

HOSTILE_TO = _register(EdgeTypeSpec(
    name="HOSTILE_TO",
    category=EdgeCategory.POLITICAL,
    direction=EdgeDirection.BIDIRECTIONAL,
    strength_property="intensity",
))

SANCTIONS_AGAINST = _register(EdgeTypeSpec(
    name="SANCTIONS_AGAINST",
    category=EdgeCategory.POLITICAL,
    direction=EdgeDirection.UNIDIRECTIONAL,
    temporal_properties=["effective_date", "sectors"],
    strength_property="sanction_type",
))

DISPUTED_BY = _register(EdgeTypeSpec(
    name="DISPUTED_BY",
    category=EdgeCategory.POLITICAL,
    direction=EdgeDirection.N_TO_M,
    strength_property="dispute_intensity",
    temporal_properties=["claim_basis"],
))

MEDIATES = _register(EdgeTypeSpec(
    name="MEDIATES",
    category=EdgeCategory.POLITICAL,
    direction=EdgeDirection.TERNARY,
))

DEPLOYED_TO = _register(EdgeTypeSpec(
    name="DEPLOYED_TO",
    category=EdgeCategory.MILITARY,
    direction=EdgeDirection.UNIDIRECTIONAL,
    temporal_properties=["since", "operational_status"],
))

COMMANDED_BY = _register(EdgeTypeSpec(
    name="COMMANDED_BY",
    category=EdgeCategory.MILITARY,
    direction=EdgeDirection.UNIDIRECTIONAL,
    temporal_properties=["chain_of_command_level"],
))

OPERATES_IN = _register(EdgeTypeSpec(
    name="OPERATES_IN",
    category=EdgeCategory.MILITARY,
    direction=EdgeDirection.UNIDIRECTIONAL,
    temporal_properties=["frequency", "purpose"],
))

ARMS_SUPPLIED_BY = _register(EdgeTypeSpec(
    name="ARMS_SUPPLIED_BY",
    category=EdgeCategory.MILITARY,
    direction=EdgeDirection.UNIDIRECTIONAL,
    temporal_properties=["weapon_types", "contract_value"],
))

TRADE_DEPENDENT_ON = _register(EdgeTypeSpec(
    name="TRADE_DEPENDENT_ON",
    category=EdgeCategory.ECONOMIC,
    direction=EdgeDirection.UNIDIRECTIONAL,
    temporal_properties=["sector"],
    strength_property="dependency_ratio",
))

ENERGY_SUPPLIED_BY = _register(EdgeTypeSpec(
    name="ENERGY_SUPPLIED_BY",
    category=EdgeCategory.ECONOMIC,
    direction=EdgeDirection.UNIDIRECTIONAL,
    temporal_properties=["energy_type", "volume"],
))

CAUSES = _register(EdgeTypeSpec(
    name="CAUSES",
    category=EdgeCategory.CAUSAL,
    direction=EdgeDirection.UNIDIRECTIONAL,
))

ENABLES = _register(EdgeTypeSpec(
    name="ENABLES",
    category=EdgeCategory.CAUSAL,
    direction=EdgeDirection.UNIDIRECTIONAL,
))

PREVENTS = _register(EdgeTypeSpec(
    name="PREVENTS",
    category=EdgeCategory.CAUSAL,
    direction=EdgeDirection.UNIDIRECTIONAL,
))

OBSERVED_AT = _register(EdgeTypeSpec(
    name="OBSERVED_AT",
    category=EdgeCategory.CAUSAL,
    direction=EdgeDirection.UNIDIRECTIONAL,
))


def get_edge_type(name: str) -> EdgeTypeSpec:
    if name not in EDGE_TYPES:
        raise KeyError(f"Unknown edge type: {name}")
    return EDGE_TYPES[name]


def list_by_category(category: EdgeCategory) -> list[EdgeTypeSpec]:
    return [e for e in EDGE_TYPES.values() if e.category == category]


def schema_for_versioning() -> list[dict]:
    """OntologyVersioning.compute_diff() 호환 포맷."""
    return [
        {"name": spec.name, "description": spec.description}
        for spec in EDGE_TYPES.values()
    ]
