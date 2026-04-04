from __future__ import annotations

import uuid

from app.graph.state import SimulationState
from app.services.event_emitter import get_emitter

TENSION_THRESHOLD = 0.6


async def check_intervention_node(state: SimulationState) -> dict:
    if state["current_round"] >= state["max_rounds"]:
        return {"decision_point": None}

    max_tension = max(state.get("tension_levels", {}).values(), default=0.0)

    if max_tension >= TENSION_THRESHOLD:
        options = []
        for code, profile in state.get("actors", {}).items():
            name = profile.get("country_name", code)
            options.append({
                "action_type": "propose_negotiation", "target": code,
                "intensity": "high", "description": f"{name}에 협상 제안",
                "estimated_effect": {"tension_delta": -0.1, "resource_cost": 0.02},
            })
            options.append({
                "action_type": "deploy_forces", "target": code,
                "intensity": "medium", "description": f"{name} 인근 병력 배치",
                "estimated_effect": {"tension_delta": +0.15, "resource_cost": 0.1},
            })

        dp = {
            "id": f"dp_{uuid.uuid4().hex[:12]}",
            "round": state["current_round"],
            "trigger": f"tension_threshold_exceeded (max={max_tension:.2f})",
            "options": options[:8],
        }
        try:
            await get_emitter().emit_intervention_required(state["scenario_id"], dp)
        except Exception:
            pass
        return {"decision_point": dp}

    return {"decision_point": None}


def should_continue(state: SimulationState) -> str:
    if state["current_round"] >= state["max_rounds"]:
        return "complete"
    if state.get("decision_point") is not None:
        return "interrupt"
    return "continue"
