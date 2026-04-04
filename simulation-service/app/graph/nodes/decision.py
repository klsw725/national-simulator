from __future__ import annotations

import logging

from app.engine import DecisionEngine
from app.graph.state import SimulationState

logger = logging.getLogger(__name__)


async def apply_decision_node(state: SimulationState) -> dict:
    user_decision = state.get("user_decision")
    if not user_decision:
        return {"user_decision": None, "decision_point": None}

    engine = DecisionEngine.from_state(state.get("decision_engine_state", {}))

    actor = user_decision.get("actor", "")
    action = user_decision.get("action_type", "do_nothing")
    if actor:
        engine.override_next_action(actor, action)

    return {
        "decision_engine_state": engine.serialize_state(),
        "user_decision": None,
        "decision_point": None,
    }
