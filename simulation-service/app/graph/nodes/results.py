from __future__ import annotations

import logging

from app.engine import DecisionEngine
from app.graph.state import SimulationState
from app.services.event_emitter import get_emitter

logger = logging.getLogger(__name__)


async def calculate_results_node(state: SimulationState) -> dict:
    old_engine_state = state.get("decision_engine_state", {})
    engine = DecisionEngine.from_state(old_engine_state)

    old_log_len = len(engine._event_log)
    round_result = engine.run_single_round(state["round_actions"])
    new_round = state["current_round"] + 1
    tensions = engine.get_tension_levels()

    try:
        max_tension = max(tensions.values()) if tensions else 0.0
        await get_emitter().emit_round_complete(
            state["scenario_id"], new_round, state["round_actions"], max_tension,
        )
    except Exception:
        pass

    new_events = [e.to_dict() for e in engine._event_log[old_log_len:]]
    round_cascades = round_result.get("cascade_events", [])

    if new_events:
        try:
            stored = await get_emitter().store_geopolitics_events(
                state["scenario_id"], new_events,
            )
            logger.info("Round %d: stored %d geopolitics events", new_round, stored)
        except Exception:
            logger.warning("Failed to store geopolitics events for round %d", new_round, exc_info=True)

    if new_events or round_cascades:
        try:
            trigger_type = "cascade_reaction" if round_cascades else "round_events"
            await get_emitter().emit_geopolitical_event(
                state["scenario_id"], new_round, trigger_type, new_events[:5],
            )
        except Exception:
            pass

    serialized = engine.serialize_state()
    serialized["extracted_entities"] = old_engine_state.get("extracted_entities", [])
    serialized["extracted_relations"] = old_engine_state.get("extracted_relations", [])

    return {
        "decision_engine_state": serialized,
        "tension_levels": tensions,
        "current_round": new_round,
        "action_history": state["action_history"] + state["round_actions"],
        "round_events": new_events,
        "round_cascades": round_cascades,
    }
