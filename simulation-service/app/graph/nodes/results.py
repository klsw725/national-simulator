from __future__ import annotations

from app.graph.state import SimulationState


async def calculate_results_node(state: SimulationState) -> dict:
    return {
        "current_round": state["current_round"] + 1,
        "action_history": state["action_history"] + state["round_actions"],
    }
