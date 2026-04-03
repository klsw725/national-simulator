from __future__ import annotations

from app.graph.state import SimulationState


async def apply_decision_node(state: SimulationState) -> dict:
    return {
        "user_decision": None,
        "decision_point": None,
    }
