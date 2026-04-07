from __future__ import annotations

import uuid

from app.graph.state import SimulationState
from langgraph.types import interrupt

TENSION_THRESHOLD = 0.6
DIRECTION_START_ROUND = 2
DIRECTION_INTERVAL = 3

HIGH_INTENSITY_TYPES = {"military_movement", "deploy_forces", "cyber_operation"}
HIGH_INTENSITY_THRESHOLD = 0.7

HIT_COOLDOWN_ROUNDS = 2

DIRECTION_OPTIONS = [
    {
        "id": "escalate",
        "label": "긴장 고조",
        "description": "군사적 대치 심화. 충돌 가능성을 탐색합니다.",
        "deltas": {"threat_perception": 0.10},
        "applies_to": "all",
    },
    {
        "id": "diplomatic",
        "label": "외교적 전환",
        "description": "외교 채널로 전환. 긴장 완화를 시도합니다.",
        "deltas": {"threat_perception": -0.10, "domestic_pressure": 0.05},
        "applies_to": "all",
    },
    {
        "id": "economic",
        "label": "경제전 전환",
        "description": "경제적 수단으로 압박을 전환합니다.",
        "deltas": {"resource_level": -0.15},
        "applies_to": "adversaries",
    },
    {
        "id": "maintain",
        "label": "현상 유지",
        "description": "현재 역학 관계를 유지하고 엔진 규칙대로 진행합니다.",
        "deltas": {},
        "applies_to": "all",
    },
]


def _is_direction_round(current_round: int) -> bool:
    if current_round < DIRECTION_START_ROUND:
        return False
    if current_round == DIRECTION_START_ROUND:
        return True
    return (current_round - DIRECTION_START_ROUND) % DIRECTION_INTERVAL == 0


def _last_hit_round(state: SimulationState) -> int:
    hit = state.get("hit_trigger")
    if isinstance(hit, dict):
        return hit.get("round", -1)
    return -1


def _build_direction_interrupt(current_round: int) -> dict:
    return {
        "id": f"dp_{uuid.uuid4().hex[:12]}",
        "type": "geopolitics_direction",
        "round": current_round,
        "trigger": "direction_checkpoint",
        "trigger_detail": None,
        "options": [
            {
                "action_type": "direction",
                "target": d["id"],
                "intensity": "medium",
                "description": f'{d["label"]}: {d["description"]}',
                "estimated_effect": {
                    "tension_delta": d["deltas"].get("threat_perception", 0),
                    "resource_cost": abs(d["deltas"].get("resource_level", 0)),
                },
                "direction": d["id"],
                "state_deltas": d["deltas"],
                "applies_to": d["applies_to"],
            }
            for d in DIRECTION_OPTIONS
        ],
    }


def _build_event_interrupt(state: SimulationState, trigger: str, source_event: dict) -> dict:
    current_round = state["current_round"]
    actors = state.get("actors", {})

    cascade_chain = []
    if trigger == "cascade_reaction":
        for cascade in state.get("round_cascades", [])[:3]:
            cascade_chain.append({
                "from": source_event.get("event_type", "unknown"),
                "to": cascade.get("event_type", "unknown"),
                "depth": cascade.get("round_number", 1),
            })

    trigger_detail = {
        "event_type": source_event.get("event_type", "unknown"),
        "source_actor": source_event.get("source_actor_id", ""),
        "target_actors": source_event.get("target_actor_ids", []),
        "magnitude": source_event.get("magnitude", 0.5),
        "description": source_event.get("description", ""),
    }
    if cascade_chain:
        trigger_detail["cascade_chain"] = cascade_chain

    options = []
    for code, profile in actors.items():
        name = profile.get("country_name", code)
        options.append({
            "action_type": "propose_negotiation",
            "target": code,
            "intensity": "high",
            "description": f"{name}에 협상 제안",
            "estimated_effect": {"tension_delta": -0.1, "resource_cost": 0.02},
        })
        options.append({
            "action_type": "deploy_forces",
            "target": code,
            "intensity": "medium",
            "description": f"{name} 인근 병력 배치",
            "estimated_effect": {"tension_delta": +0.15, "resource_cost": 0.1},
        })

    return {
        "id": f"dp_{uuid.uuid4().hex[:12]}",
        "round": current_round,
        "trigger": trigger,
        "trigger_detail": trigger_detail,
        "actor_states_snapshot": {
            aid: astate for aid, astate in state.get("actor_states", {}).items()
        },
        "options": options[:8],
    }


def _build_tension_interrupt(state: SimulationState, max_tension: float) -> dict:
    dp = _build_event_interrupt(
        state,
        "tension_threshold_exceeded",
        {
            "event_type": "tension_threshold",
            "source_actor_id": "",
            "target_actor_ids": list(state.get("actors", {}).keys()),
            "magnitude": max_tension,
            "description": f"최대 긴장도 {max_tension:.2f} — 임계값 초과",
        },
    )
    dp["type"] = "geopolitics_actor_response"
    return dp


async def evaluate_events_node(state: SimulationState) -> dict:
    if state["current_round"] >= state["max_rounds"]:
        return {
            "decision_point": None,
            "user_decision": None,
            "hit_trigger": None,
            "round_events": [],
            "round_cascades": [],
        }

    last_hit = _last_hit_round(state)
    cooldown_active = (
        last_hit >= 0
        and (state["current_round"] - last_hit) < HIT_COOLDOWN_ROUNDS
    )

    round_cascades = state.get("round_cascades", [])
    round_events = state.get("round_events", [])

    if not cooldown_active:
        # Trigger 1: cascade reaction
        if round_cascades:
            dp = _build_event_interrupt(state, "cascade_reaction", round_events[0] if round_events else round_cascades[0])
            user_decision = interrupt(dp)
            return {
                "user_decision": user_decision,
                "decision_point": None,
                "hit_trigger": dp,
                "status": "running",
            }

        # Trigger 2: high-intensity military action
        for evt in round_events:
            if (
                evt.get("event_type") in HIGH_INTENSITY_TYPES
                and evt.get("magnitude", 0) >= HIGH_INTENSITY_THRESHOLD
            ):
                dp = _build_event_interrupt(state, "high_intensity_military", evt)
                user_decision = interrupt(dp)
                return {
                    "user_decision": user_decision,
                    "decision_point": None,
                    "hit_trigger": dp,
                    "status": "running",
                }

    # Trigger 3: tension threshold (always checked, no cooldown)
    max_tension = max(state.get("tension_levels", {}).values(), default=0.0)
    if max_tension >= TENSION_THRESHOLD:
        dp = _build_tension_interrupt(state, max_tension)
        user_decision = interrupt(dp)
        return {
            "user_decision": user_decision,
            "decision_point": None,
            "hit_trigger": dp,
            "status": "running",
        }

    # Trigger 4: direction checkpoint (always checked, no cooldown)
    if _is_direction_round(state["current_round"]):
        dp = _build_direction_interrupt(state["current_round"])
        user_decision = interrupt(dp)
        return {
            "user_decision": user_decision,
            "decision_point": None,
            "hit_trigger": dp,
            "status": "running",
        }

    return {"decision_point": None, "user_decision": None, "hit_trigger": None}


def should_continue(state: SimulationState) -> str:
    if state["current_round"] >= state["max_rounds"]:
        return "complete"
    if state.get("user_decision") is not None:
        return "apply_decision"
    return "continue"
