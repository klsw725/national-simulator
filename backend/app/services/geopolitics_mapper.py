from __future__ import annotations

import re

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

_CONTENT_REPLACEMENTS = [
    (re.compile(r"CREATE_POST", re.IGNORECASE), "공식 성명 발표"),
    (re.compile(r"QUOTE_POST", re.IGNORECASE), "공식 반응"),
    (re.compile(r"LIKE_POST", re.IGNORECASE), "암묵적 동의"),
    (re.compile(r"DO_NOTHING", re.IGNORECASE), "전략적 관망"),
    (re.compile(r"(?<![가-힣])REPOST(?![가-힣])", re.IGNORECASE), "동맹 지지 표명"),
    (re.compile(r"(?<![가-힣])FOLLOW(?![가-힣])", re.IGNORECASE), "외교적 연계 강화"),
    (re.compile(r"(공식\s*)?(트위터|Twitter|엑스)\s*(공식\s*)?(계정|채널)?", re.IGNORECASE), "공식 채널"),
    (re.compile(r"(공식\s*)?위챗\s*(공식\s*)?(계정|채널)?"), "공식 채널"),
    (re.compile(r"(틱톡|TikTok)", re.IGNORECASE), "영상 채널"),
    (re.compile(r"(유튜브|YouTube)", re.IGNORECASE), "영상 채널"),
    (re.compile(r"(인스타그램|Instagram)", re.IGNORECASE), "공식 채널"),
    (re.compile(r"(페이스북|Facebook)", re.IGNORECASE), "공식 채널"),
    (re.compile(r"리트윗"), "지지 표명"),
    (re.compile(r"리포스트"), "지지 표명"),
    (re.compile(r"트윗"), "성명"),
    (re.compile(r"좋아요"), "암묵적 동의"),
    (re.compile(r"팔로우"), "외교적 연계"),
    (re.compile(r"해시태그"), "정책 키워드"),
    (re.compile(r"소셜\s*미디어"), "공개 정보 채널"),
    (re.compile(r"SNS"), "공식 채널"),
    (re.compile(r"#(\w+)"), r"[\1]"),
]


def transform_content(text: str) -> str:
    if not text:
        return text
    result = text
    for pattern, replacement in _CONTENT_REPLACEMENTS:
        result = pattern.sub(replacement, result)
    return result


def map_actions_to_geopolitics(
    actions: list[dict],
    source_filter: str | None = None,
) -> list[dict]:
    mapped = []
    seen_event_types_this_round: set[str] = set()

    for action in actions:
        action_copy = dict(action)
        metadata = action_copy.get("metadata")
        source = metadata.get("source") if isinstance(metadata, dict) else None

        if source_filter is not None and source != source_filter:
            continue

        if source in {"geo_event", "user_decision"}:
            continue

        raw_type = (action_copy.get("action_type") or "").lower()
        geo_type = GEOPOLITICS_ACTION_MAP.get(raw_type, raw_type)

        if geo_type in seen_event_types_this_round:
            continue

        seen_event_types_this_round.add(geo_type)
        action_copy["geopolitics_action"] = geo_type
        action_copy["geopolitics_label"] = GEOPOLITICS_LABELS.get(geo_type, geo_type)

        for field in ("content", "post_content", "text"):
            if field in action_copy and action_copy[field]:
                action_copy[field] = transform_content(str(action_copy[field]))

        mapped.append(action_copy)
    return mapped
