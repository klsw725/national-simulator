from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class GeopoliticsEvent:
    event_type: str  # military_movement, sanction_impose, diplomatic_statement, treaty_sign, trade_restriction, military_exercise
    source_actor_id: str
    target_actor_ids: list[str] = field(default_factory=list)
    magnitude: float = 0.5  # 0.0–1.0
    description: str = ""
    round_number: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GeopoliticsEvent:
        return cls(**data)


# ---------------------------------------------------------------------------
# Propagation rules: event_type → state changes on target actors
# ---------------------------------------------------------------------------

PROPAGATION_RULES: dict[str, dict[str, float]] = {
    "military_movement": {
        "threat_perception": +0.15,
        "domestic_pressure": +0.05,
    },
    "military_exercise": {
        "threat_perception": +0.10,
    },
    "sanction_impose": {
        "resource_level": -0.20,
        "domestic_pressure": +0.15,
    },
    "trade_restriction": {
        "resource_level": -0.10,
        "domestic_pressure": +0.10,
    },
    "diplomatic_statement": {
        "threat_perception": +0.05,
    },
    "treaty_sign": {
        "threat_perception": -0.10,
        "domestic_pressure": -0.05,
    },
}
