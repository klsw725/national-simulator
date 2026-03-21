from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Objective:
    name: str
    priority: float  # 0.0–1.0
    description: str = ""


@dataclass
class Constraint:
    name: str
    hard: bool = True  # hard=절대 위반 불가, soft=비용 증가
    description: str = ""


@dataclass
class GeopoliticalActorState:
    """M1: 국가/비국가 행위자의 상태 모델.

    PRD §3.2 필드 + 직렬화.
    """

    actor_id: str
    name: str
    actor_type: str = "state"  # state / non_state / igo
    country_code: str = ""

    # 동적 상태 (0.0–1.0)
    threat_perception: float = 0.0
    domestic_pressure: float = 0.0
    resource_level: float = 1.0

    # 목표/제약/현재 행동
    objectives: list[Objective] = field(default_factory=list)
    constraints: list[Constraint] = field(default_factory=list)
    active_actions: list[str] = field(default_factory=list)

    # 관계
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
