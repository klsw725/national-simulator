from __future__ import annotations

import logging

from app.engine import DecisionEngine
from app.graph.state import SimulationState

logger = logging.getLogger(__name__)


async def calculate_results_node(state: SimulationState) -> dict:
    engine = DecisionEngine.from_state(state.get("decision_engine_state", {}))
    engine.run_single_round(state["round_actions"])

    return {
        "decision_engine_state": engine.serialize_state(),
        "tension_levels": engine.get_tension_levels(),
        "current_round": state["current_round"] + 1,
        "action_history": state["action_history"] + state["round_actions"],
    }
