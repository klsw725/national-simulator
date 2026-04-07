from __future__ import annotations

from typing import Annotated, TypedDict

from langgraph.graph import add_messages


class SimulationState(TypedDict):
    scenario_id: str
    seed_text: str
    region_bbox: list[float]
    region_name: str
    question: str

    ontology_version: str
    graph_id: str
    situation_summary: str

    actors: dict[str, dict]
    actor_states: dict[str, dict]

    current_round: int
    max_rounds: int
    round_actions: list[dict]
    action_history: list[dict]

    tension_levels: dict[str, float]
    decision_engine_state: dict

    decision_point: dict | None
    user_decision: dict | None

    round_events: list[dict]
    round_cascades: list[dict]
    hit_trigger: dict | None

    phase: str
    status: str
    messages: Annotated[list, add_messages]
