from __future__ import annotations

from langgraph.types import interrupt

from app.graph.state import SimulationState


def _checkpoint_payload(state: SimulationState, step: str) -> dict:
    data = {
        "scenario_id": state["scenario_id"],
        "question": state.get("question", ""),
        "region_name": state.get("region_name", ""),
        "current_round": state.get("current_round", 0),
        "max_rounds": state.get("max_rounds", 10),
        "situation_summary": state.get("situation_summary", ""),
        "actors": state.get("actors", {}),
        "actor_states": state.get("actor_states", {}),
        "tension_levels": state.get("tension_levels", {}),
        "graph_entities": state.get("graph_entities", []),
        "graph_relations": state.get("graph_relations", []),
        "phase": state.get("phase", ""),
        "status": state.get("status", ""),
        "seed_text": state.get("seed_text", ""),
    }
    return {
        "type": "pipeline_checkpoint",
        "step": step,
        "state": data,
    }


def _pause_if_needed(state: SimulationState, step: str) -> dict:
    if state.get("pipeline_mode") != "checkpoint":
        return {}
    completed = state.get("completed_checkpoints", [])
    if step in completed:
        return {}
    interrupt(_checkpoint_payload(state, step))
    return {"completed_checkpoints": completed + [step]}


async def review_relations_checkpoint(state: SimulationState) -> dict:
    return _pause_if_needed(state, "seed")


async def review_profiles_checkpoint(state: SimulationState) -> dict:
    return _pause_if_needed(state, "graph")


async def review_config_checkpoint(state: SimulationState) -> dict:
    return _pause_if_needed(state, "profiles")


async def review_geopolitics_checkpoint(state: SimulationState) -> dict:
    return _pause_if_needed(state, "config")
