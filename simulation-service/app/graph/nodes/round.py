from __future__ import annotations

import asyncio
import logging

from app.graph.state import SimulationState
from app.llm import llm_json
from app.prompts.actor_system import ACTOR_SYSTEM_PROMPT
from app.services.event_emitter import get_emitter
from app.services.osint_injector import fetch_latest_osint, format_osint_for_prompt

logger = logging.getLogger(__name__)


async def _call_agent(actor_code: str, state: SimulationState, osint_text: str) -> list[dict]:
    profile = state["actors"].get(actor_code, {})
    actor_state = state["actor_states"].get(actor_code, {})

    recent_actions = [
        a for a in state["action_history"][-20:] if a.get("actor") != actor_code
    ]
    other_actions_text = "\n".join(
        f"- {a.get('actor', '?')}: {a.get('action_type', '?')} → {a.get('target', '?')}"
        for a in recent_actions[-10:]
    ) or "없음"

    system_prompt = ACTOR_SYSTEM_PROMPT.format(
        country_name=profile.get("country_name", actor_code),
        military_power=profile.get("military_power", "unknown"),
        economic_power=profile.get("economic_power", "unknown"),
        ideology=profile.get("ideology", "unknown"),
        alliances=", ".join(profile.get("alliances", [])),
        core_interests=", ".join(profile.get("core_interests", [])),
        behavior_tendency=profile.get("behavior_tendency", "unknown"),
        situation_summary=state["situation_summary"][:1500],
        recent_osint=osint_text[:1000],
        other_actions=other_actions_text,
        tension=actor_state.get("threat_perception", 0.0),
        resources=actor_state.get("resource_level", 1.0),
        domestic_pressure=actor_state.get("domestic_pressure", 0.0),
    )

    try:
        actions = await llm_json(
            system=system_prompt,
            user=f"라운드 {state['current_round'] + 1}: 행동을 결정하십시오.",
            temperature=0.7,
            max_tokens=1000,
        )
        if not isinstance(actions, list):
            actions = [actions] if isinstance(actions, dict) else []
        for action in actions:
            action["actor"] = actor_code
        return actions[:3]
    except Exception:
        logger.exception("Agent %s failed", actor_code)
        return [{"actor": actor_code, "action_type": "do_nothing", "target": "none",
                 "intensity": "low", "reasoning": "LLM 호출 실패"}]


async def run_round_node(state: SimulationState) -> dict:
    osint = await fetch_latest_osint()
    osint_text = format_osint_for_prompt(osint)

    tasks = [_call_agent(code, state, osint_text) for code in state["actors"]]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    round_actions: list[dict] = []
    for result in results:
        if isinstance(result, BaseException):
            logger.error("Agent call failed: %s", result)
            continue
        for action in result:
            round_actions.append(action)

    try:
        emitter = get_emitter()
        for action in round_actions:
            await emitter.emit_agent_action(state["scenario_id"], state["current_round"] + 1, action)
    except Exception:
        pass

    return {"round_actions": round_actions}
