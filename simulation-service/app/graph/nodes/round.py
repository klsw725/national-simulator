from __future__ import annotations

from app.graph.state import SimulationState


async def run_round_node(state: SimulationState) -> dict:
    return {
        "round_actions": [
            {
                "actor": "stub",
                "action_type": "do_nothing",
                "target": "none",
                "intensity": "low",
                "reasoning": "Stub round — no agent logic yet",
            },
        ],
    }
