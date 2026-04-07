from __future__ import annotations

from app.graph.state import SimulationState
from app.services.event_emitter import get_emitter


async def configure_sim_node(state: SimulationState) -> dict:
    try:
        await get_emitter().emit_phase_change(state["scenario_id"], "simulating", 0.6)
    except Exception:
        pass
    return {
        "current_round": 0,
        "round_actions": [],
        "action_history": [],
        "tension_levels": {code: 0.0 for code in state.get("actors", {})},
        "decision_point": None,
        "user_decision": None,
        "round_events": [],
        "round_cascades": [],
        "hit_trigger": None,
        "phase": "simulating",
    }
