from __future__ import annotations

import asyncio
import logging

from app.engine.actors import GeopoliticalActorState
from app.graph.state import SimulationState
from app.llm import llm_json
from app.prompts.actor_system import ACTOR_PROFILE_PROMPT
from app.services.event_emitter import get_emitter

logger = logging.getLogger(__name__)

_PROFILE_RETRY = 3
_PROFILE_DELAY = 2.0

KNOWN_ACTORS: dict[str, str] = {
    "US": "미국", "CN": "중국", "RU": "러시아", "KR": "한국",
    "JP": "일본", "KP": "북한", "TW": "대만", "IN": "인도",
    "PH": "필리핀", "VN": "베트남", "AU": "호주", "GB": "영국",
    "FR": "프랑스", "DE": "독일", "IR": "이란", "SA": "사우디아라비아",
    "AE": "아랍에미리트", "OM": "오만", "IQ": "이라크",
}

POWER_TO_RESOURCE: dict[str, float] = {
    "superpower": 0.95, "major": 0.8, "regional": 0.6, "minor": 0.4,
}

REGION_DEFAULT_ACTORS: dict[str, list[str]] = {
    "strait of hormuz": ["IR", "SA", "AE", "OM", "US"],
    "hormuz": ["IR", "SA", "AE", "OM", "US"],
    "south china sea": ["CN", "PH", "VN", "US", "TW"],
    "taiwan strait": ["CN", "TW", "US", "JP"],
    "east china sea": ["CN", "JP", "KR", "US"],
    "korean peninsula": ["KR", "KP", "US", "JP", "CN"],
}


def _select_actor_codes(state: SimulationState) -> list[str]:
    actor_codes = list(state.get("actor_states", {}).keys())
    if actor_codes:
        return actor_codes

    extracted_entities = state.get("decision_engine_state", {}).get("extracted_entities", [])
    for entity in extracted_entities:
        entity_type = str(entity.get("type", "")).lower()
        entity_id = str(entity.get("id", "")).upper()
        if "nation" in entity_type and entity_id in KNOWN_ACTORS and entity_id not in actor_codes:
            actor_codes.append(entity_id)

    if actor_codes:
        return actor_codes

    region_name = str(state.get("region_name", "")).lower()
    for key, defaults in REGION_DEFAULT_ACTORS.items():
        if key in region_name:
            return defaults

    return ["US", "IR", "SA"] if region_name else ["US", "CN", "KR"]


def _infer_relationships(
    actor_code: str,
    all_profiles: dict[str, dict],
    extracted_relations: list[dict],
) -> tuple[list[str], list[str]]:
    allies: list[str] = []
    adversaries: list[str] = []

    profile = all_profiles.get(actor_code, {})
    alliance_list = profile.get("alliances", [])

    for other_code in all_profiles:
        if other_code == actor_code:
            continue
        if other_code in alliance_list:
            allies.append(other_code)

    for rel in extracted_relations:
        src, tgt = rel.get("source", ""), rel.get("target", "")
        rtype = rel.get("type", "")
        strength = rel.get("strength", 0.5)

        if actor_code not in (src, tgt):
            continue
        other = tgt if src == actor_code else src

        if rtype in ("ALLIED_WITH", "TRADE_DEPENDENT_ON", "ENERGY_SUPPLIED_BY") and strength >= 0.5:
            if other not in allies:
                allies.append(other)
        elif rtype in ("HOSTILE_TO", "SANCTIONS_AGAINST") and strength >= 0.4:
            if other not in adversaries:
                adversaries.append(other)

    return allies, adversaries


async def create_actors_node(state: SimulationState) -> dict:
    try:
        await get_emitter().emit_phase_change(state["scenario_id"], "configuring", 0.4)
    except Exception:
        pass
    actor_codes = _select_actor_codes(state)

    extracted_relations = state.get("decision_engine_state", {}).get("extracted_relations", [])

    actors: dict[str, dict] = {}
    actor_states: dict[str, dict] = {}
    engine_actors: dict[str, dict] = {}

    for code in actor_codes[:10]:
        actor_name = KNOWN_ACTORS.get(code, code)
        prompt = ACTOR_PROFILE_PROMPT.format(actor_code=code, actor_name=actor_name)
        last_exc: Exception | None = None
        profile: dict | None = None
        delay = _PROFILE_DELAY

        for attempt in range(_PROFILE_RETRY):
            try:
                result = await llm_json(
                    system="당신은 지정학 전문가입니다.",
                    user=f"{prompt}\n\n정세 요약:\n{state['situation_summary'][:1500]}",
                    temperature=0.4,
                )
                if isinstance(result, dict) and result:
                    profile = result
                    break
                last_exc = RuntimeError("LLM returned empty/invalid profile")
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "Profile generation failed for %s (attempt %d/%d): %s",
                    code,
                    attempt + 1,
                    _PROFILE_RETRY,
                    str(exc)[:200],
                )
            if attempt < _PROFILE_RETRY - 1:
                await asyncio.sleep(delay)
                delay *= 2

        if profile is None:
            try:
                await get_emitter().emit_phase_change(state["scenario_id"], "failed", 0.4)
            except Exception:
                pass
            raise RuntimeError(
                f"Actor profile generation failed for {code} after {_PROFILE_RETRY} attempts: {last_exc}"
            )

        actors[code] = profile

    for code in actor_codes[:10]:
        actor_name = KNOWN_ACTORS.get(code, code)
        profile = actors.get(code, {})
        allies, adversaries = _infer_relationships(code, actors, extracted_relations)

        military = profile.get("military_power", "regional")
        economic = profile.get("economic_power", "regional")
        tendency = profile.get("behavior_tendency", "defensive")

        initial_threat = 0.5 if adversaries else 0.2
        initial_pressure = 0.4 if tendency == "aggressive" else 0.2

        gs = GeopoliticalActorState(
            actor_id=code,
            name=actor_name,
            country_code=code,
            resource_level=POWER_TO_RESOURCE.get(economic, 0.6),
            threat_perception=initial_threat,
            domestic_pressure=initial_pressure,
            allies=allies,
            adversaries=adversaries,
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
