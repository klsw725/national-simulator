from __future__ import annotations

import logging

from app.engine import DecisionEngine
from app.graph.nodes.intervene import DIRECTION_OPTIONS
from app.graph.state import SimulationState

logger = logging.getLogger(__name__)

_DIRECTION_LOOKUP: dict[str, dict] = {d["id"]: d for d in DIRECTION_OPTIONS}


async def apply_decision_node(state: SimulationState) -> dict:
    user_decision = state.get("user_decision")
    if not user_decision:
        return {"user_decision": None, "decision_point": None}

    engine_state = dict(state.get("decision_engine_state", {}))
    engine = DecisionEngine.from_state(engine_state)

    if user_decision.get("action_type") == "direction":
        direction_id = user_decision.get("target", "")
        direction_def = _DIRECTION_LOOKUP.get(direction_id)
        if direction_def and direction_def["deltas"]:
            engine.apply_direction_deltas(
                direction_def["deltas"],
                direction_def["applies_to"],
            )
            logger.info(
                "Applied direction '%s' (applies_to=%s, deltas=%s)",
                direction_id, direction_def["applies_to"], direction_def["deltas"],
            )

        return {
            "decision_engine_state": {
                **engine.serialize_state(),
                "extracted_entities": engine_state.get("extracted_entities", []),
                "extracted_relations": engine_state.get("extracted_relations", []),
            },
            "user_decision": None,
            "decision_point": None,
            "round_events": [],
            "round_cascades": [],
        }

    actor = user_decision.get("actor", "")
    action = user_decision.get("action_type", "do_nothing")
    if actor:
        engine.override_next_action(actor, action)
    overrides = dict(engine_state.get("action_overrides", {}))
    if actor:
        overrides[actor] = user_decision

    return {
        "decision_engine_state": {
            **engine.serialize_state(),
            "action_overrides": overrides,
            "extracted_entities": engine_state.get("extracted_entities", []),
            "extracted_relations": engine_state.get("extracted_relations", []),
        },
        "user_decision": None,
        "decision_point": None,
        "round_events": [],
        "round_cascades": [],
    }
