from __future__ import annotations

import json
import logging
import re

from app.graph.state import SimulationState
from app.llm import llm_chat
from app.prompts.actor_system import SITUATION_ANALYSIS_PROMPT
from app.services.event_emitter import get_emitter
from app.services.osint_injector import fetch_latest_osint, format_osint_for_prompt

logger = logging.getLogger(__name__)


async def analyze_situation_node(state: SimulationState) -> dict:
    try:
        await get_emitter().emit_phase_change(state["scenario_id"], "analyzing", 0)
    except Exception:
        pass
    osint = await fetch_latest_osint(region_bbox=state.get("region_bbox"))
    osint_text = format_osint_for_prompt(osint)
    user_prompt = (
        f"## 지역\n{state.get('region_name', '')}\n\n"
        f"## 질문\n{state.get('question', '')}\n\n"
        f"## 시나리오 시드\n{state['seed_text']}\n\n"
        f"## 실시간 OSINT 데이터\n{osint_text}"
    )

    response = await llm_chat(
        system=SITUATION_ANALYSIS_PROMPT,
        user=user_prompt,
        temperature=0.5,
        max_tokens=3000,
    )

    actor_codes: list[str] = []
    match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", response)
    if match:
        try:
            parsed = json.loads(match.group(1))
            actor_codes = parsed.get("actors", [])
        except json.JSONDecodeError:
            pass
        summary = response[:match.start()].strip()
    else:
        summary = response

    return {
        "situation_summary": summary,
        "phase": "analyzing",
        "status": "running",
        "actor_states": {code: {} for code in actor_codes},
    }
