from __future__ import annotations

from app.graph.state import SimulationState


async def configure_sim_node(state: SimulationState) -> dict:
    return {
        "current_round": 0,
        "round_actions": [],
        "action_history": [],
        "tension_levels": {code: 0.0 for code in state.get("actors", {})},
        "decision_point": None,
        "user_decision": None,
        "phase": "simulating",
    }
