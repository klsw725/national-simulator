from __future__ import annotations

import asyncio
import logging

from app.graph.state import SimulationState
from app.llm import llm_json
from app.prompts.actor_system import ENTITY_EXTRACTION_PROMPT
from app.services.event_emitter import get_emitter
from app.services.graph_store import get_graph_store

logger = logging.getLogger(__name__)

_EXTRACT_RETRY = 3
_EXTRACT_DELAY = 2.0


async def build_relations_node(state: SimulationState) -> dict:
    try:
        await get_emitter().emit_phase_change(state["scenario_id"], "building", 0.2)
    except Exception:
        pass

    last_exc: Exception | None = None
    entities: list = []
    relations: list = []
    delay = _EXTRACT_DELAY

    for attempt in range(_EXTRACT_RETRY):
        try:
            result = await llm_json(
                system=ENTITY_EXTRACTION_PROMPT,
                user=state["situation_summary"],
                temperature=0.3,
            )
            entities = result.get("entities", []) if isinstance(result, dict) else []
            relations = result.get("relations", []) if isinstance(result, dict) else []
            if entities:
                break
            last_exc = RuntimeError("LLM returned empty entities")
            logger.warning(
                "Entity extraction returned empty entities (attempt %d/%d)",
                attempt + 1,
                _EXTRACT_RETRY,
            )
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "Entity extraction failed (attempt %d/%d): %s",
                attempt + 1,
                _EXTRACT_RETRY,
                str(exc)[:200],
            )
        if attempt < _EXTRACT_RETRY - 1:
            await asyncio.sleep(delay)
            delay *= 2

    if not entities:
        try:
            await get_emitter().emit_phase_change(state["scenario_id"], "failed", 0.2)
        except Exception:
            pass
        raise RuntimeError(
            f"Graph generation failed after {_EXTRACT_RETRY} attempts: {last_exc}"
        )

    graph_id = f"graph_{state['scenario_id']}"
    store = get_graph_store()
    counts = store.store_entities_and_relations(graph_id, entities, relations)
    logger.info(
        "DozerDB stored: %d entities, %d relations",
        counts["entities"],
        counts["relations"],
    )

    try:
        await get_emitter()._emit({
            "type": "graph_data",
            "scenario_id": state["scenario_id"],
            "entities": entities,
            "relations": relations,
        })
    except Exception:
        logger.warning("graph_data emit failed", exc_info=True)

    return {
        "graph_id": graph_id,
        "graph_entities": entities,
        "graph_relations": relations,
        "phase": "building",
        "decision_engine_state": {
            "actors": {},
            "event_log": [],
            "round": 0,
            "extracted_entities": entities,
            "extracted_relations": relations,
        },
    }
