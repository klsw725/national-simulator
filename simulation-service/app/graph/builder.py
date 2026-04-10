from __future__ import annotations

import logging

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph

from app.config import settings
from app.graph.nodes.actors import create_actors_node
from app.graph.nodes.analyze import analyze_situation_node
from app.graph.nodes.checkpoints import (
    review_config_checkpoint,
    review_geopolitics_checkpoint,
    review_profiles_checkpoint,
    review_relations_checkpoint,
)
from app.graph.nodes.configure import configure_sim_node
from app.graph.nodes.decision import apply_decision_node
from app.graph.nodes.intervene import evaluate_events_node, should_continue
from app.graph.nodes.relations import build_relations_node
from app.graph.nodes.report import generate_report_node
from app.graph.nodes.results import calculate_results_node
from app.graph.nodes.round import run_round_node
from app.graph.state import SimulationState

logger = logging.getLogger(__name__)

_checkpointer_cm = None
_checkpointer = None
_compiled_graphs: dict[str, object] = {}


def _build_sim_loop() -> StateGraph:
    g = StateGraph(SimulationState)
    g.add_node("run_round", run_round_node)
    g.add_node("calculate_results", calculate_results_node)
    g.add_node("evaluate_events", evaluate_events_node)
    g.add_node("apply_decision", apply_decision_node)

    g.add_edge(START, "run_round")
    g.add_edge("run_round", "calculate_results")
    g.add_edge("calculate_results", "evaluate_events")
    g.add_conditional_edges("evaluate_events", should_continue, {
        "continue": "run_round",
        "apply_decision": "apply_decision",
        "complete": END,
    })
    g.add_edge("apply_decision", "run_round")
    return g


def _build_parent(sim_loop_compiled) -> StateGraph:
    g = StateGraph(SimulationState)
    g.add_node("analyze_situation", analyze_situation_node)
    g.add_node("review_relations_checkpoint", review_relations_checkpoint)
    g.add_node("build_relations", build_relations_node)
    g.add_node("review_profiles_checkpoint", review_profiles_checkpoint)
    g.add_node("create_actors", create_actors_node)
    g.add_node("review_config_checkpoint", review_config_checkpoint)
    g.add_node("configure_sim", configure_sim_node)
    g.add_node("review_geopolitics_checkpoint", review_geopolitics_checkpoint)
    g.add_node("simulation_loop", sim_loop_compiled)
    g.add_node("generate_report", generate_report_node)

    g.add_edge(START, "analyze_situation")
    g.add_edge("analyze_situation", "review_relations_checkpoint")
    g.add_edge("review_relations_checkpoint", "build_relations")
    g.add_edge("build_relations", "review_profiles_checkpoint")
    g.add_edge("review_profiles_checkpoint", "create_actors")
    g.add_edge("create_actors", "review_config_checkpoint")
    g.add_edge("review_config_checkpoint", "configure_sim")
    g.add_edge("configure_sim", "review_geopolitics_checkpoint")
    g.add_edge("review_geopolitics_checkpoint", "simulation_loop")
    g.add_edge("simulation_loop", "generate_report")
    g.add_edge("generate_report", END)
    return g


async def get_graph(mode: str = "auto"):
    global _checkpointer_cm, _checkpointer
    if _checkpointer is None:
        _checkpointer_cm = AsyncPostgresSaver.from_conn_string(settings.database_url)
        _checkpointer = await _checkpointer_cm.__aenter__()
        await _checkpointer.setup()

    if mode in _compiled_graphs:
        return _compiled_graphs[mode]

    sim_loop = _build_sim_loop().compile(checkpointer=_checkpointer)
    parent = _build_parent(sim_loop)

    compiled = parent.compile(checkpointer=_checkpointer)

    _compiled_graphs[mode] = compiled
    return compiled
