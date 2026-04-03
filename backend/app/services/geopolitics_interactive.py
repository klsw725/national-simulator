from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from app.database import get_pool
from app.geopolitics.actors import GeopoliticalActorState
from app.geopolitics.engine import DecisionEngine, POSSIBLE_ACTIONS
from app.geopolitics.events import PROPAGATION_RULES
from app.models.scenario import GeopoliticsMode

logger = logging.getLogger(__name__)


ACTION_LABELS = {
    "military_movement": "군사 대응",
    "military_exercise": "군사 훈련",
    "sanction_impose": "경제 제재",
    "trade_restriction": "무역 제한",
    "diplomatic_statement": "외교 성명",
    "treaty_sign": "조약 제안",
    "do_nothing": "관망",
}

ACTION_DESCRIPTIONS = {
    "military_movement": "상대 위협에 동등 수준 군사력으로 대응합니다.",
    "military_exercise": "군사 훈련으로 억지력을 과시하되 직접 대치는 피합니다.",
    "sanction_impose": "경제 제재를 부과하여 상대 자원을 압박합니다.",
    "trade_restriction": "무역 제한으로 경제적 압박을 가합니다.",
    "diplomatic_statement": "공개 성명으로 입장을 표명하고 외교 채널을 활용합니다.",
    "treaty_sign": "동맹국과의 협력을 강화하고 긴장 완화를 시도합니다.",
    "do_nothing": "현 상황을 유지하며 추가 정보를 수집합니다.",
}

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


def should_pause(
    round_result: dict,
    mode: GeopoliticsMode,
    player_actor_id: str | None,
    threshold: float = 0.5,
    pause_interval: int = 3,
) -> bool:
    if mode == GeopoliticsMode.AUTO:
        return False

    events = round_result.get("events", []) + round_result.get("cascade_events", [])

    if mode == GeopoliticsMode.ACTOR_ROLE:
        if not player_actor_id:
            return False

        return any(
            (
                event.get("source_actor_id") == player_actor_id
                or player_actor_id in event.get("target_actor_ids", [])
            )
            and float(event.get("magnitude", 0.0)) >= threshold
            for event in events
        )

    current_round = int(round_result.get("round") or 0)
    if current_round < 2:
        return False

    if current_round == 2:
        return True

    if pause_interval > 1 and (current_round - 2) % pause_interval != 0:
        return False

    cascade_events = round_result.get("cascade_events", [])
    if cascade_events:
        return True

    magnitudes = [max(0.0, float(event.get("magnitude", 0.0))) for event in events]
    high_impact_count = sum(1 for magnitude in magnitudes if magnitude >= threshold)
    cumulative_magnitude = sum(magnitudes)

    return high_impact_count >= 2 or cumulative_magnitude >= (threshold * 2)


def build_actor_response_options(
    engine: DecisionEngine,
    actor_id: str,
    trigger_event: dict,
) -> list[dict]:
    actor: GeopoliticalActorState | None = engine.get_actor(actor_id)
    if actor is None:
        return []

    engine_recommended = engine._decide_single(actor)
    trigger_type = trigger_event.get("event_type", "unknown")
    trigger_magnitude = float(trigger_event.get("magnitude", 0.0))

    options: list[dict] = []
    for action in POSSIBLE_ACTIONS:
        is_recommended = action == engine_recommended
        reasoning = ""
        if is_recommended:
            reasoning = (
                f"엔진 추천 행동입니다. 트리거 이벤트({trigger_type}, 규모 {trigger_magnitude:.2f})와 "
                f"현재 상태(threat_perception={actor.threat_perception:.2f}, "
                f"domestic_pressure={actor.domestic_pressure:.2f}, "
                f"resource_level={actor.resource_level:.2f})를 기준으로 가장 적합합니다."
            )

        options.append(
            {
                "id": action,
                "label": ACTION_LABELS.get(action, action),
                "description": ACTION_DESCRIPTIONS.get(action, ""),
                "confidence": 0.85 if is_recommended else 0.0,
                "reasoning": reasoning,
                "data": {
                    "action": action,
                    "predicted_deltas": PROPAGATION_RULES.get(action, {}),
                    "engine_recommended": is_recommended,
                },
            },
        )

    return options


def build_direction_options(round_result: dict) -> list[dict]:
    _ = round_result
    options: list[dict] = []
    for direction in DIRECTION_OPTIONS:
        options.append(
            {
                "id": direction["id"],
                "label": direction["label"],
                "description": direction["description"],
                "confidence": 0.0,
                "reasoning": "",
                "data": {
                    "direction": direction["id"],
                    "state_deltas": direction["deltas"],
                    "applies_to": direction["applies_to"],
                },
            },
        )
    return options


def find_trigger_event(round_result: dict, player_actor_id: str) -> dict | None:
    events = round_result.get("events", []) + round_result.get("cascade_events", [])
    best_event: dict | None = None
    best_magnitude = -1.0

    for event in events:
        involved = (
            event.get("source_actor_id") == player_actor_id
            or player_actor_id in event.get("target_actor_ids", [])
        )
        if not involved:
            continue

        magnitude = float(event.get("magnitude", 0.0))
        if magnitude > best_magnitude:
            best_event = event
            best_magnitude = magnitude

    return best_event


async def save_geopolitics_snapshot(
    scenario_id: str,
    result_id: str,
    round_number: int,
    engine: DecisionEngine,
    mode: GeopoliticsMode,
    player_actor_id: str | None,
) -> str:
    snapshot_id = f"gs_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    engine_state = json.dumps(engine.serialize_state(), ensure_ascii=False)

    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO geopolitics_snapshots
               (id, scenario_id, result_id, round_number, engine_state, pending_decision_point_id, geopolitics_mode, player_actor_id, created_at)
               VALUES ($1, $2, $3, $4, $5, NULL, $6, $7, $8)""",
            snapshot_id,
            scenario_id,
            result_id,
            round_number,
            engine_state,
            mode.value,
            player_actor_id,
            now,
        )

    logger.debug(
        "Saved geopolitics snapshot: id=%s scenario=%s result=%s round=%d",
        snapshot_id,
        scenario_id,
        result_id,
        round_number,
    )
    return snapshot_id


async def get_latest_snapshot(scenario_id: str, result_id: str) -> dict | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT * FROM geopolitics_snapshots
               WHERE scenario_id = $1 AND result_id = $2
               ORDER BY round_number DESC
               LIMIT 1""",
            scenario_id,
            result_id,
        )

    return dict(row) if row else None


async def link_snapshot_to_dp(snapshot_id: str, dp_id: str) -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE geopolitics_snapshots SET pending_decision_point_id = $1 WHERE id = $2",
            dp_id,
            snapshot_id,
        )


async def create_geopolitics_decision_point(
    scenario_id: str,
    dp_type: str,
    options: list[dict],
    recommended: str,
) -> str:
    dp_id = f"dp_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    options_json = json.dumps(options, ensure_ascii=False)

    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO decision_points
               (id, scenario_id, type, options, recommended, allow_custom, status, selected_option_id, custom_data, created_at, resolved_at)
               VALUES ($1, $2, $3, $4, $5, TRUE, 'pending', NULL, NULL, $6, NULL)""",
            dp_id,
            scenario_id,
            dp_type,
            options_json,
            recommended,
            now,
        )

    logger.debug(
        "Created geopolitics decision point: id=%s scenario=%s type=%s",
        dp_id,
        scenario_id,
        dp_type,
    )
    return dp_id
