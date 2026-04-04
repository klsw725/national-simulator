from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Objective:
    name: str
    priority: float
    description: str = ""


@dataclass
class Constraint:
    name: str
    hard: bool = True
    description: str = ""


@dataclass
class GeopoliticalActorState:
    actor_id: str
    name: str
    actor_type: str = "state"
    country_code: str = ""

    threat_perception: float = 0.0
    domestic_pressure: float = 0.0
    resource_level: float = 1.0

    objectives: list[Objective] = field(default_factory=list)
    constraints: list[Constraint] = field(default_factory=list)
    active_actions: list[str] = field(default_factory=list)

    allies: list[str] = field(default_factory=list)
    adversaries: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GeopoliticalActorState:
        objectives = [Objective(**o) if isinstance(o, dict) else o for o in data.pop("objectives", [])]
        constraints = [Constraint(**c) if isinstance(c, dict) else c for c in data.pop("constraints", [])]
        return cls(objectives=objectives, constraints=constraints, **data)

    def clamp_state(self) -> None:
        self.threat_perception = max(0.0, min(1.0, self.threat_perception))
        self.domestic_pressure = max(0.0, min(1.0, self.domestic_pressure))
        self.resource_level = max(0.0, min(1.0, self.resource_level))
