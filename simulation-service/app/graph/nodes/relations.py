from __future__ import annotations

import logging

from app.graph.state import SimulationState
from app.llm import llm_json
from app.prompts.actor_system import ENTITY_EXTRACTION_PROMPT

logger = logging.getLogger(__name__)


async def build_relations_node(state: SimulationState) -> dict:
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

    return {
        "graph_id": f"graph_{state['scenario_id']}",
        "phase": "building",
        "decision_engine_state": {
            "actors": {},
            "event_log": [],
            "round": 0,
            "extracted_entities": entities,
            "extracted_relations": relations,
        },
    }
