from __future__ import annotations

import logging

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph

from app.config import settings
from app.graph.nodes.actors import create_actors_node
from app.graph.nodes.analyze import analyze_situation_node
from app.graph.nodes.configure import configure_sim_node
from app.graph.nodes.decision import apply_decision_node
from app.graph.nodes.intervene import check_intervention_node, should_continue
from app.graph.nodes.relations import build_relations_node
from app.graph.nodes.report import generate_report_node
from app.graph.nodes.results import calculate_results_node
from app.graph.nodes.round import run_round_node
from app.graph.state import SimulationState

logger = logging.getLogger(__name__)

_builder = StateGraph(SimulationState)

_builder.add_node("analyze_situation", analyze_situation_node)
_builder.add_node("build_relations", build_relations_node)
_builder.add_node("create_actors", create_actors_node)
_builder.add_node("configure_sim", configure_sim_node)
_builder.add_node("run_round", run_round_node)
_builder.add_node("calculate_results", calculate_results_node)
_builder.add_node("check_intervention", check_intervention_node)
_builder.add_node("apply_decision", apply_decision_node)
_builder.add_node("generate_report", generate_report_node)

_builder.add_edge(START, "analyze_situation")
_builder.add_edge("analyze_situation", "build_relations")
_builder.add_edge("build_relations", "create_actors")
_builder.add_edge("create_actors", "configure_sim")
_builder.add_edge("configure_sim", "run_round")
_builder.add_edge("run_round", "calculate_results")
_builder.add_edge("calculate_results", "check_intervention")
_builder.add_conditional_edges("check_intervention", should_continue, {
    "continue": "run_round",
    "interrupt": END,
    "complete": "generate_report",
})
_builder.add_edge("apply_decision", "run_round")
_builder.add_edge("generate_report", END)


async def get_graph():
    checkpointer = AsyncPostgresSaver.from_conn_string(settings.database_url)
    await checkpointer.setup()
    return _builder.compile(
        checkpointer=checkpointer,
        interrupt_before=["check_intervention"],
    )
