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
    try:
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
        actions = await llm_json(
            system=system_prompt,
            user=f"라운드 {state['current_round'] + 1}: 행동을 결정하십시오.",
            temperature=0.7,
            max_tokens=1000,
        )
        if not isinstance(actions, list):
            actions = [actions] if isinstance(actions, dict) else []
        validated = []
        for action in actions[:3]:
            if not isinstance(action, dict):
                continue
            action.setdefault("actor", actor_code)
            action.setdefault("action_type", "do_nothing")
            action.setdefault("target", "none")
            action.setdefault("intensity", "low")
            action.setdefault("reasoning", "")
            action["actor"] = actor_code
            validated.append(action)
        return validated if validated else [{"actor": actor_code, "action_type": "do_nothing",
                                             "target": "none", "intensity": "low", "reasoning": "파싱 결과 없음"}]
    except Exception as exc:
        logger.warning("Agent %s JSON parse failed: %s", actor_code, str(exc)[:200])
        return [{"actor": actor_code, "action_type": "do_nothing", "target": "none",
                 "intensity": "low", "reasoning": f"LLM 파싱 실패: {str(exc)[:100]}"}]


async def run_round_node(state: SimulationState) -> dict:
    osint = await fetch_latest_osint(region_bbox=state.get("region_bbox"))
    osint_text = format_osint_for_prompt(osint)
    overrides = dict(state.get("decision_engine_state", {}).get("action_overrides", {}))

    tasks = [_call_agent(code, state, osint_text) for code in state["actors"]]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    round_actions: list[dict] = []
    for result in results:
        if isinstance(result, BaseException):
            logger.error("Agent call failed: %s", result)
            continue
        for action in result:
            round_actions.append(action)

    if overrides:
        round_actions = [a for a in round_actions if a.get("actor") not in overrides]
        for actor, override in overrides.items():
            if not isinstance(override, dict):
                continue
            round_actions.append({
                "actor": actor,
                "action_type": override.get("action_type", "do_nothing"),
                "target": override.get("target", "none"),
                "intensity": override.get("intensity", "medium"),
                "reasoning": override.get("reasoning", "사용자 개입 결정 반영"),
            })

    try:
        emitter = get_emitter()
        for action in round_actions:
            await emitter.emit_agent_action(state["scenario_id"], state["current_round"] + 1, action)
    except Exception:
        pass

    next_engine_state = dict(state.get("decision_engine_state", {}))
    if "action_overrides" in next_engine_state:
        next_engine_state["action_overrides"] = {}

    return {
        "round_actions": round_actions,
        "decision_engine_state": next_engine_state,
    }
