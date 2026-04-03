from __future__ import annotations

from app.graph.state import SimulationState


async def build_relations_node(state: SimulationState) -> dict:
    return {
        "graph_id": "stub_graph",
        "phase": "building",
    }
