from __future__ import annotations

from app.graph.state import SimulationState


async def analyze_situation_node(state: SimulationState) -> dict:
    return {
        "situation_summary": state["seed_text"],
        "phase": "analyzing",
        "status": "running",
    }
