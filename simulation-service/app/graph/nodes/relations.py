from __future__ import annotations

import logging

from app.graph.state import SimulationState
from app.llm import llm_json
from app.prompts.actor_system import ENTITY_EXTRACTION_PROMPT
from app.services.event_emitter import get_emitter
from app.services.graph_store import get_graph_store

logger = logging.getLogger(__name__)


async def build_relations_node(state: SimulationState) -> dict:
    try:
        await get_emitter().emit_phase_change(state["scenario_id"], "building", 0.2)
    except Exception:
        pass
    try:
        result = await llm_json(
            system=ENTITY_EXTRACTION_PROMPT,
            user=state["situation_summary"],
            temperature=0.3,
        )
        entities = result.get("entities", []) if isinstance(result, dict) else []
        relations = result.get("relations", []) if isinstance(result, dict) else []
    except Exception:
        logger.exception("Entity extraction failed, using empty graph")
        entities = []
        relations = []

    graph_id = f"graph_{state['scenario_id']}"

    try:
        store = get_graph_store()
        counts = store.store_entities_and_relations(graph_id, entities, relations)
        logger.info("DozerDB stored: %d entities, %d relations", counts["entities"], counts["relations"])
    except Exception:
        logger.exception("DozerDB store failed — continuing without graph persistence")

    try:
        await get_emitter()._emit({
            "type": "graph_data",
            "scenario_id": state["scenario_id"],
            "entities": entities,
            "relations": relations,
        })
    except Exception:
        pass

    return {
        "graph_id": graph_id,
        "phase": "building",
        "decision_engine_state": {
            "actors": {},
            "event_log": [],
            "round": 0,
            "extracted_entities": entities,
            "extracted_relations": relations,
        },
    }
