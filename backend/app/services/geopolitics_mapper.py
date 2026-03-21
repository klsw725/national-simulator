from __future__ import annotations

GEOPOLITICS_ACTION_MAP = {
    "create_post": "diplomatic_statement",
    "quote_post": "official_response",
    "repost": "alliance_support",
    "like_post": "tacit_approval",
    "follow": "diplomatic_engagement",
    "do_nothing": "strategic_observation",
}

GEOPOLITICS_LABELS = {
    "diplomatic_statement": "공식 성명 발표",
    "official_response": "타국 성명에 대한 공식 반응",
    "alliance_support": "동맹국 입장 지지/전파",
    "tacit_approval": "타국 입장에 대한 암묵적 동의",
    "diplomatic_engagement": "외교적 관계 형성 의사",
    "strategic_observation": "전략적 관망/무반응",
}


def map_actions_to_geopolitics(actions: list[dict]) -> list[dict]:
    mapped = []
    for action in actions:
        action_copy = dict(action)
        raw_type = (action_copy.get("action_type") or "").lower()
        geo_type = GEOPOLITICS_ACTION_MAP.get(raw_type, raw_type)
        action_copy["geopolitics_action"] = geo_type
        action_copy["geopolitics_label"] = GEOPOLITICS_LABELS.get(geo_type, geo_type)
        mapped.append(action_copy)
    return mapped
