from __future__ import annotations

import logging

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph

from app.config import settings
from app.graph.nodes.actors import create_actors_node
from app.graph.nodes.analyze import analyze_situation_node
from app.graph.nodes.configure import configure_sim_node
from app.graph.nodes.decision import apply_decision_node
from app.graph.nodes.intervene import evaluate_events_node, should_continue
from app.graph.nodes.relations import build_relations_node
from app.graph.nodes.report import generate_report_node
from app.graph.nodes.results import calculate_results_node
from app.graph.nodes.round import run_round_node
from app.graph.state import SimulationState

logger = logging.getLogger(__name__)

_sim_loop = StateGraph(SimulationState)
_sim_loop.add_node("run_round", run_round_node)
_sim_loop.add_node("calculate_results", calculate_results_node)
_sim_loop.add_node("evaluate_events", evaluate_events_node)
_sim_loop.add_node("apply_decision", apply_decision_node)

_sim_loop.add_edge(START, "run_round")
_sim_loop.add_edge("run_round", "calculate_results")
_sim_loop.add_edge("calculate_results", "evaluate_events")
_sim_loop.add_conditional_edges("evaluate_events", should_continue, {
    "continue": "run_round",
    "apply_decision": "apply_decision",
    "complete": END,
})
_sim_loop.add_edge("apply_decision", "run_round")

_builder = StateGraph(SimulationState)

_builder.add_node("analyze_situation", analyze_situation_node)
_builder.add_node("build_relations", build_relations_node)
_builder.add_node("create_actors", create_actors_node)
_builder.add_node("configure_sim", configure_sim_node)
_builder.add_node("simulation_loop", _sim_loop.compile())
_builder.add_node("generate_report", generate_report_node)

_builder.add_edge(START, "analyze_situation")
_builder.add_edge("analyze_situation", "build_relations")
_builder.add_edge("build_relations", "create_actors")
_builder.add_edge("create_actors", "configure_sim")
_builder.add_edge("configure_sim", "simulation_loop")
_builder.add_edge("simulation_loop", "generate_report")
_builder.add_edge("generate_report", END)


_checkpointer_cm = None
_checkpointer = None


async def get_graph():
    global _checkpointer_cm, _checkpointer
    _checkpointer_cm = AsyncPostgresSaver.from_conn_string(settings.database_url)
    _checkpointer = await _checkpointer_cm.__aenter__()
    await _checkpointer.setup()
    return _builder.compile(
        checkpointer=_checkpointer,
    )
