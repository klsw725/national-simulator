from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.geopolitics.actors import GeopoliticalActorState, Objective, Constraint
from app.geopolitics.engine import DecisionEngine
from app.geopolitics.events import GeopoliticsEvent

router = APIRouter(prefix="/api/geopolitics", tags=["geopolitics"])


class ActorInput(BaseModel):
    actor_id: str
    name: str
    actor_type: str = "state"
    country_code: str = ""
    threat_perception: float = 0.0
    domestic_pressure: float = 0.0
    resource_level: float = 1.0
    objectives: list[dict[str, Any]] = Field(default_factory=list)
    constraints: list[dict[str, Any]] = Field(default_factory=list)
    allies: list[str] = Field(default_factory=list)
    adversaries: list[str] = Field(default_factory=list)


class SimulateRequest(BaseModel):
    actors: list[ActorInput]
    rounds: int = 5


class EventInjectRequest(BaseModel):
    actors: list[ActorInput]
    event_type: str
    source_actor_id: str
    target_actor_ids: list[str]
    magnitude: float = 0.5
    description: str = ""


def _build_actor(inp: ActorInput) -> GeopoliticalActorState:
    return GeopoliticalActorState(
        actor_id=inp.actor_id,
        name=inp.name,
        actor_type=inp.actor_type,
        country_code=inp.country_code,
        threat_perception=inp.threat_perception,
        domestic_pressure=inp.domestic_pressure,
        resource_level=inp.resource_level,
        objectives=[Objective(**o) for o in inp.objectives],
        constraints=[Constraint(**c) for c in inp.constraints],
        allies=inp.allies,
        adversaries=inp.adversaries,
    )


@router.post("/simulate")
async def run_simulation(data: SimulateRequest):
    if len(data.actors) < 2:
        raise HTTPException(status_code=400, detail="At least 2 actors required")
    if data.rounds < 1 or data.rounds > 50:
        raise HTTPException(status_code=400, detail="rounds must be 1-50")

    engine = DecisionEngine()
    for actor_input in data.actors:
        engine.add_actor(_build_actor(actor_input))

    result = engine.run_simulation(data.rounds)
    return result


@router.post("/event")
async def inject_event(data: EventInjectRequest):
    engine = DecisionEngine()
    for actor_input in data.actors:
        engine.add_actor(_build_actor(actor_input))

    event = GeopoliticsEvent(
        event_type=data.event_type,
        source_actor_id=data.source_actor_id,
        target_actor_ids=data.target_actor_ids,
        magnitude=data.magnitude,
        description=data.description,
    )

    deltas, cascades = engine.apply_event_with_cascade(event)

    return {
        "event": event.to_dict(),
        "state_changes": deltas,
        "cascade_events": [e.to_dict() for e in cascades],
        "actor_states": {a.actor_id: a.to_dict() for a in engine.get_all_actors()},
    }
