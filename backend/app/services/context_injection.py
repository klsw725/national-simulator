from __future__ import annotations

from app.geopolitics.engine import DecisionEngine


EVENT_POST_TEMPLATES: dict[str, dict[str, str]] = {
    "military_movement": {
        "author": "@DefenseIntel",
        "template": "{source_actor} 군이 {target_region} 방면으로 병력 이동을 개시했습니다. 군사 전문가들은 이를 {assessment}으로 분석하고 있습니다.",
    },
    "military_exercise": {
        "author": "@MilitaryWatch",
        "template": "{source_actor}이(가) {target_region}에서 대규모 군사훈련을 실시합니다. 훈련 규모: {magnitude_desc}.",
    },
    "sanction_impose": {
        "author": "@EconAlert",
        "template": "속보: {source_actor}이(가) {target_actor}에 대한 경제 제재를 발동했습니다. 대상: {sanction_detail}.",
    },
    "trade_restriction": {
        "author": "@TradeMonitor",
        "template": "{source_actor}이(가) {target_actor}에 대한 무역 제한 조치를 시행합니다. {restriction_detail}.",
    },
    "diplomatic_statement": {
        "author": "@DiplomaticBrief",
        "template": "{source_actor} 외교부 성명: \"{statement_content}\"",
    },
    "treaty_sign": {
        "author": "@TreatyWatch",
        "template": "{source_actor}와(과) {target_actor}이(가) {treaty_type} 협정에 서명했습니다.",
    },
}

DECISION_POST_TEMPLATES: dict[str, str | None] = {
    "military_movement": "{actor} 정부가 군사적 대응을 결정했습니다. 군 관계자에 따르면 병력 이동이 시작되었습니다.",
    "military_exercise": "{actor} 정부가 군사 훈련 실시를 승인했습니다.",
    "sanction_impose": "{actor} 정부가 경제 제재 시행을 공식 발표했습니다.",
    "trade_restriction": "{actor} 정부가 무역 제한 조치를 시행하기로 결정했습니다.",
    "diplomatic_statement": "{actor} 외교부가 공식 성명을 발표하여 외교적 해결을 촉구했습니다.",
    "treaty_sign": "{actor} 정부가 동맹 강화를 위한 새로운 협정 체결을 추진합니다.",
    "do_nothing": None,
}

MAGNITUDE_DESCRIPTIONS: dict[tuple[float, float], str] = {
    (0.0, 0.3): "소규모",
    (0.3, 0.6): "중규모",
    (0.6, 0.8): "대규모",
    (0.8, 1.0): "전례 없는 규모의",
}


def _get_magnitude_description(magnitude: float) -> str:
    value = max(0.0, min(1.0, magnitude))
    for (lower, upper), description in MAGNITUDE_DESCRIPTIONS.items():
        if lower <= value < upper:
            return description
    return "전례 없는 규모의"


def _resolve_actor_name(engine: DecisionEngine, actor_id: str, fallback: str) -> str:
    actor = engine.get_actor(actor_id)
    return actor.name if actor else fallback


def _render_event_post(template: str, event: dict, engine: DecisionEngine) -> str:
    source_actor_id = event.get("source_actor_id", "")
    target_actor_ids = event.get("target_actor_ids", [])
    magnitude = float(event.get("magnitude", 0.0))
    source_actor = _resolve_actor_name(engine, source_actor_id, "해당 국가")

    target_names = [
        _resolve_actor_name(engine, target_id, target_id)
        for target_id in target_actor_ids
    ]
    target_actor = ", ".join(target_names) if target_names else "주변국"

    return template.format(
        source_actor=source_actor,
        target_actor=target_actor,
        target_region=target_actor,
        magnitude_desc=_get_magnitude_description(magnitude),
        assessment="군사적 신호",
        sanction_detail="핵심 산업 및 금융 부문",
        restriction_detail="핵심 전략 품목 수출 통제 포함",
        statement_content=event.get("description") or "지역 안정을 위한 외교적 해법을 촉구한다",
        treaty_type="안보 협력",
    )


def _append_system_post(
    system_posts: list[dict],
    *,
    author: str,
    content: str,
    metadata: dict,
) -> None:
    for platform in ("twitter", "reddit"):
        system_posts.append(
            {
                "platform": platform,
                "author": author,
                "content": content,
                "metadata": dict(metadata),
            },
        )


def _build_env_constraints(
    events: list[dict],
    user_decision: dict | None = None,
) -> list[dict]:
    constraints: list[dict] = []

    if user_decision:
        action = str(user_decision.get("action") or "").strip().lower()
        actor_ref = user_decision.get("actor_id") or user_decision.get("actor_name")
        if actor_ref and action and action != "do_nothing":
            constraints.append(
                {
                    "type": "block_action",
                    "target_agents": [actor_ref],
                    "blocked_actions": ["create_post"],
                    "duration_rounds": 1,
                    "reason": f"previous_decision:{action}: 공식 입장 반복 발표 억제",
                },
            )

    for event in events:
        if not isinstance(event, dict):
            continue
        source_actor = str(event.get("source_actor_id") or "").strip()
        if not source_actor:
            continue
        event_type = str(event.get("event_type") or "").strip().lower()
        magnitude = float(event.get("magnitude") or 0.0)

        if event_type in {"military_movement", "military_exercise"} and magnitude >= 0.5:
            constraints.append(
                {
                    "type": "block_action",
                    "target_agents": [source_actor],
                    "blocked_actions": ["create_post"],
                    "duration_rounds": 1,
                    "reason": f"high_tension:{event_type}: 반복 선전성 게시 억제",
                },
            )
        elif event_type in {"sanction_impose", "trade_restriction"}:
            constraints.append(
                {
                    "type": "block_action",
                    "target_agents": [source_actor],
                    "blocked_actions": ["create_post"],
                    "duration_rounds": 1,
                    "reason": f"policy_enforcement:{event_type}: 제재/무역조치 직후 발언 제한",
                },
            )

    return constraints


def build_inject_context(
    engine: DecisionEngine,
    round_result: dict,
    user_decision: dict | None = None,
) -> dict:
    system_posts: list[dict] = []
    events = round_result.get("events", []) + round_result.get("cascade_events", [])

    current_round = int(round_result.get("round") or getattr(engine, "_round", 0))

    for event in events:
        event_type = event.get("event_type", "")
        template_info = EVENT_POST_TEMPLATES.get(event_type)
        if not template_info:
            continue

        content = _render_event_post(template_info["template"], event, engine)
        event_round = int(event.get("round_number") or current_round)

        _append_system_post(
            system_posts,
            author=template_info["author"],
            content=content,
            metadata={
                "source": "geo_event",
                "event_type": event_type,
                "event_id": event.get("id", ""),
                "round": event_round,
            },
        )

    if user_decision:
        raw_action = user_decision.get("action")
        action = raw_action if isinstance(raw_action, str) else ""
        actor_name = user_decision.get("actor_name", "해당 국가")
        template = DECISION_POST_TEMPLATES.get(action)
        if template:
            _append_system_post(
                system_posts,
                author="@OfficialStatement",
                content=template.format(actor=actor_name),
                metadata={
                    "source": "user_decision",
                    "action": action,
                    "round": current_round,
                },
            )

    env_constraints = _build_env_constraints(events, user_decision=user_decision)
    return {"system_posts": system_posts, "env_constraints": env_constraints}
