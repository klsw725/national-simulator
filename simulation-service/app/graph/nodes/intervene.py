from __future__ import annotations

from app.graph.state import SimulationState


async def check_intervention_node(state: SimulationState) -> dict:
    return {"decision_point": None}


def should_continue(state: SimulationState) -> str:
    if state["current_round"] >= state["max_rounds"]:
        return "complete"
    if state.get("decision_point") is not None:
        return "interrupt"
    return "continue"
