from __future__ import annotations

import logging

from app.engine.actors import GeopoliticalActorState
from app.graph.state import SimulationState
from app.llm import llm_json
from app.prompts.actor_system import ACTOR_PROFILE_PROMPT

logger = logging.getLogger(__name__)

KNOWN_ACTORS: dict[str, str] = {
    "US": "미국", "CN": "중국", "RU": "러시아", "KR": "한국",
    "JP": "일본", "KP": "북한", "TW": "대만", "IN": "인도",
    "PH": "필리핀", "VN": "베트남", "AU": "호주", "GB": "영국",
    "FR": "프랑스", "DE": "독일", "IR": "이란", "SA": "사우디아라비아",
}


async def create_actors_node(state: SimulationState) -> dict:
    actor_codes = list(state.get("actor_states", {}).keys())
    if not actor_codes:
        actor_codes = ["US", "CN", "KR"]

    actors: dict[str, dict] = {}
    actor_states: dict[str, dict] = {}
    engine_actors: dict[str, dict] = {}

    for code in actor_codes[:10]:
        actor_name = KNOWN_ACTORS.get(code, code)
        try:
            prompt = ACTOR_PROFILE_PROMPT.format(
                actor_code=code, actor_name=actor_name,
            )
            profile = await llm_json(
                system="당신은 지정학 전문가입니다.",
                user=f"{prompt}\n\n정세 요약:\n{state['situation_summary'][:1500]}",
                temperature=0.4,
            )
            if isinstance(profile, dict):
                actors[code] = profile
        except Exception:
            logger.warning("Failed to generate profile for %s, using defaults", code)
            actors[code] = {
                "nation_code": code,
                "country_name": actor_name,
                "military_power": "regional",
                "economic_power": "regional",
                "ideology": "unknown",
                "alliances": [],
                "core_interests": [],
                "behavior_tendency": "defensive",
            }

        gs = GeopoliticalActorState(
            actor_id=code, name=actor_name, country_code=code,
        )
        actor_states[code] = gs.to_dict()
        engine_actors[code] = gs.to_dict()

    engine_state = state.get("decision_engine_state", {})
    engine_state["actors"] = engine_actors

    return {
        "actors": actors,
        "actor_states": actor_states,
        "decision_engine_state": engine_state,
        "phase": "configuring",
    }
