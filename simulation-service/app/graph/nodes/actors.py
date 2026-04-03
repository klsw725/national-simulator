from __future__ import annotations

from app.graph.state import SimulationState


async def create_actors_node(state: SimulationState) -> dict:
    return {
        "actors": {},
        "actor_states": {},
        "phase": "configuring",
    }
