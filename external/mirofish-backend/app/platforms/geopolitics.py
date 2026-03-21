GEOPOLITICS_ACTION_MAP = {
    "create_post": "diplomatic_statement",
    "quote_post": "official_response",
    "repost": "alliance_support",
    "like_post": "tacit_approval",
    "follow": "diplomatic_engagement",
    "do_nothing": "strategic_observation",
}

GEOPOLITICS_ACTION_LABELS = {
    "diplomatic_statement": "공식 성명 발표",
    "official_response": "타국 성명에 대한 공식 반응",
    "alliance_support": "동맹국 입장 지지/전파",
    "tacit_approval": "타국 입장에 대한 암묵적 동의",
    "diplomatic_engagement": "외교적 관계 형성 의사",
    "strategic_observation": "전략적 관망/무반응",
}

ACTOR_TYPES = {
    "superpower": {
        "military_capability": 0.95,
        "economic_power": 0.9,
        "diplomatic_influence": 0.95,
    },
    "regional_power": {
        "military_capability": 0.7,
        "economic_power": 0.7,
        "diplomatic_influence": 0.6,
    },
    "small_state": {
        "military_capability": 0.3,
        "economic_power": 0.3,
        "diplomatic_influence": 0.3,
    },
    "military_alliance": {
        "military_capability": 0.9,
        "economic_power": 0.5,
        "diplomatic_influence": 0.8,
    },
    "international_org": {
        "military_capability": 0.0,
        "economic_power": 0.4,
        "diplomatic_influence": 0.9,
    },
}

GEOPOLITICS_PERSONA_PROMPT = """\
당신은 소셜미디어 플랫폼에서 국가/기관의 공식 계정을 운영합니다.
각 행동의 의미:

- 포스트 작성 (CREATE_POST): 공식 성명 또는 입장 발표
- 인용 포스트 (QUOTE_POST): 타국 성명에 대한 공식 반응/논평
- 리포스트 (REPOST): 동맹국 성명 지지/전파
- 좋아요 (LIKE_POST): 타국 성명에 대한 암묵적 동의
- 팔로우 (FOLLOW): 외교적 관계 형성 의사 표시
- 아무것도 안 함 (DO_NOTHING): 전략적 관망/무반응

중요 규칙:
- 당신의 발언은 해당 국가/기관의 공식 입장을 반영해야 합니다
- 현실 국제관계의 동맹/적대 구도를 반영하세요
- 군사적 위협은 외교적 언어로 표현하세요
- 경제적 이해관계를 고려한 반응을 보이세요
"""


def map_actions_to_geopolitics(actions: list[dict]) -> list[dict]:
    mapped = []
    for action in actions:
        a = dict(action)
        raw_type = (a.get("action_type") or "").lower()
        geo_type = GEOPOLITICS_ACTION_MAP.get(raw_type, raw_type)
        a["geopolitics_action"] = geo_type
        a["geopolitics_label"] = GEOPOLITICS_ACTION_LABELS.get(geo_type, geo_type)
        mapped.append(a)
    return mapped


def build_geopolitics_profile(
    user_id: int,
    name: str,
    actor_type: str = "regional_power",
    country_code: str = "",
    alliances: list[str] | None = None,
    adversaries: list[str] | None = None,
    persona: str = "",
) -> dict:
    type_attrs = ACTOR_TYPES.get(actor_type, ACTOR_TYPES["regional_power"])

    full_persona = persona
    if not full_persona:
        alliance_text = f"동맹: {', '.join(alliances)}" if alliances else ""
        adversary_text = f"적대: {', '.join(adversaries)}" if adversaries else ""
        full_persona = f"{name}은(는) {actor_type} 유형의 국제 행위자입니다. {alliance_text} {adversary_text}".strip()

    return {
        "user_id": user_id,
        "username": name.replace(" ", "_").lower(),
        "name": name,
        "bio": f"{actor_type} | {country_code}",
        "persona": f"{full_persona}\n\n{GEOPOLITICS_PERSONA_PROMPT}",
        "friend_count": 100,
        "follower_count": 150,
        "statuses_count": 500,
        "actor_type": actor_type,
        "country_code": country_code,
        "military_capability": type_attrs["military_capability"],
        "economic_power": type_attrs["economic_power"],
        "diplomatic_influence": type_attrs["diplomatic_influence"],
        "alliances": alliances or [],
        "adversaries": adversaries or [],
    }
