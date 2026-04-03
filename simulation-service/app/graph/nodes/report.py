from __future__ import annotations

from app.graph.state import SimulationState


async def generate_report_node(state: SimulationState) -> dict:
    total_rounds = state["current_round"]
    total_actions = len(state["action_history"])
    return {
        "phase": "reporting",
        "status": "completed",
        "situation_summary": (
            f"[Stub Report] Simulation completed: {total_rounds} rounds, "
            f"{total_actions} actions recorded."
        ),
    }
