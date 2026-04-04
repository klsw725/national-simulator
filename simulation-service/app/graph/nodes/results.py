from __future__ import annotations

import logging

from app.engine import DecisionEngine
from app.graph.state import SimulationState
from app.services.event_emitter import get_emitter

logger = logging.getLogger(__name__)


async def calculate_results_node(state: SimulationState) -> dict:
    engine = DecisionEngine.from_state(state.get("decision_engine_state", {}))
    engine.run_single_round(state["round_actions"])
    new_round = state["current_round"] + 1
    tensions = engine.get_tension_levels()

    try:
        max_tension = max(tensions.values()) if tensions else 0.0
        await get_emitter().emit_round_complete(
            state["scenario_id"], new_round, state["round_actions"], max_tension,
        )
    except Exception:
        pass

    return {
        "decision_engine_state": engine.serialize_state(),
        "tension_levels": tensions,
        "current_round": new_round,
        "action_history": state["action_history"] + state["round_actions"],
    }
