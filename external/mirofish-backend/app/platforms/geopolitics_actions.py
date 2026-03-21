from __future__ import annotations

from enum import Enum


class GeopoliticsActionType(str, Enum):
    """OASIS ActionType 확장 — 지정학 전용 행동 타입.

    기존 OASIS 소셜미디어 ActionType과 병렬로 사용.
    OASIS ActionType과 동일한 str Enum 패턴을 따른다.
    """

    # 외교
    DIPLOMATIC_STATEMENT = "diplomatic_statement"
    OFFICIAL_RESPONSE = "official_response"
    TREATY_SIGN = "treaty_sign"

    # 군사
    MILITARY_MOVEMENT = "military_movement"
    MILITARY_EXERCISE = "military_exercise"

    # 경제
    SANCTION_IMPOSE = "sanction_impose"
    SANCTION_LIFT = "sanction_lift"
    TRADE_RESTRICTION = "trade_restriction"

    # 동맹/적대
    ALLIANCE_SUPPORT = "alliance_support"
    TACIT_APPROVAL = "tacit_approval"
    DIPLOMATIC_ENGAGEMENT = "diplomatic_engagement"

    # 관망
    STRATEGIC_OBSERVATION = "strategic_observation"


# OASIS 소셜 액션 → 지정학 액션 매핑 (기존 geopolitics.py와 통합)
SOCIAL_TO_GEOPOLITICS: dict[str, GeopoliticsActionType] = {
    "create_post": GeopoliticsActionType.DIPLOMATIC_STATEMENT,
    "quote_post": GeopoliticsActionType.OFFICIAL_RESPONSE,
    "repost": GeopoliticsActionType.ALLIANCE_SUPPORT,
    "like_post": GeopoliticsActionType.TACIT_APPROVAL,
    "follow": GeopoliticsActionType.DIPLOMATIC_ENGAGEMENT,
    "do_nothing": GeopoliticsActionType.STRATEGIC_OBSERVATION,
}

# 지정학 액션 → 한국어 레이블
GEOPOLITICS_ACTION_LABELS_EXTENDED: dict[str, str] = {
    "diplomatic_statement": "공식 성명 발표",
    "official_response": "타국 성명에 대한 공식 반응",
    "treaty_sign": "조약/협정 체결",
    "military_movement": "군사 이동/배치",
    "military_exercise": "군사 훈련 실시",
    "sanction_impose": "제재 발동",
    "sanction_lift": "제재 해제",
    "trade_restriction": "무역 제한 조치",
    "alliance_support": "동맹국 입장 지지",
    "tacit_approval": "암묵적 동의",
    "diplomatic_engagement": "외교적 관계 형성",
    "strategic_observation": "전략적 관망",
}
