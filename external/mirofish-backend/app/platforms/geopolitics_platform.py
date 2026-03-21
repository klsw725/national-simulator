"""GeopoliticsPlatform — OASIS Platform 서브클래스 패턴.

OASIS Platform의 getattr(self, action.value) 디스패치를 활용하여
지정학 액션 핸들러를 메서드로 등록한다.

OASIS가 설치된 환경에서는 Platform을 상속하고,
미설치 환경에서는 독립적으로 동작한다.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from app.platforms.geopolitics_actions import (
    GeopoliticsActionType,
    GEOPOLITICS_ACTION_LABELS_EXTENDED,
)

logger = logging.getLogger(__name__)

try:
    from oasis.social.platform import Platform as OASISPlatform
    _HAS_OASIS = True
except ImportError:
    OASISPlatform = object  # type: ignore[assignment,misc]
    _HAS_OASIS = False


class GeopoliticsPlatform(OASISPlatform):  # type: ignore[misc]
    """지정학 행위자 시뮬레이션 플랫폼.

    OASIS Twitter/Reddit Platform과 동일한 인터페이스를 따른다.
    getattr(self, action_type.value) 디스패치로 각 액션 핸들러가 호출된다.
    """

    def __init__(self, event_callback: Any = None) -> None:
        if _HAS_OASIS:
            super().__init__()
        self._events: list[dict[str, Any]] = []
        self._round: int = 0
        self._event_callback = event_callback

    def set_round(self, round_number: int) -> None:
        self._round = round_number

    def get_events(self) -> list[dict[str, Any]]:
        return list(self._events)

    def clear_events(self) -> None:
        self._events.clear()

    # ------------------------------------------------------------------
    # Action handlers — OASIS dispatches via getattr(self, action.value)
    # ------------------------------------------------------------------

    async def diplomatic_statement(self, actor_id: str, content: str = "", **kwargs: Any) -> dict[str, Any]:
        return self._record_event(GeopoliticsActionType.DIPLOMATIC_STATEMENT, actor_id, content, kwargs)

    async def official_response(self, actor_id: str, content: str = "", **kwargs: Any) -> dict[str, Any]:
        return self._record_event(GeopoliticsActionType.OFFICIAL_RESPONSE, actor_id, content, kwargs)

    async def treaty_sign(self, actor_id: str, content: str = "", **kwargs: Any) -> dict[str, Any]:
        return self._record_event(GeopoliticsActionType.TREATY_SIGN, actor_id, content, kwargs)

    async def military_movement(self, actor_id: str, content: str = "", **kwargs: Any) -> dict[str, Any]:
        return self._record_event(GeopoliticsActionType.MILITARY_MOVEMENT, actor_id, content, kwargs)

    async def military_exercise(self, actor_id: str, content: str = "", **kwargs: Any) -> dict[str, Any]:
        return self._record_event(GeopoliticsActionType.MILITARY_EXERCISE, actor_id, content, kwargs)

    async def sanction_impose(self, actor_id: str, content: str = "", **kwargs: Any) -> dict[str, Any]:
        return self._record_event(GeopoliticsActionType.SANCTION_IMPOSE, actor_id, content, kwargs)

    async def sanction_lift(self, actor_id: str, content: str = "", **kwargs: Any) -> dict[str, Any]:
        return self._record_event(GeopoliticsActionType.SANCTION_LIFT, actor_id, content, kwargs)

    async def trade_restriction(self, actor_id: str, content: str = "", **kwargs: Any) -> dict[str, Any]:
        return self._record_event(GeopoliticsActionType.TRADE_RESTRICTION, actor_id, content, kwargs)

    async def alliance_support(self, actor_id: str, content: str = "", **kwargs: Any) -> dict[str, Any]:
        return self._record_event(GeopoliticsActionType.ALLIANCE_SUPPORT, actor_id, content, kwargs)

    async def tacit_approval(self, actor_id: str, content: str = "", **kwargs: Any) -> dict[str, Any]:
        return self._record_event(GeopoliticsActionType.TACIT_APPROVAL, actor_id, content, kwargs)

    async def diplomatic_engagement(self, actor_id: str, content: str = "", **kwargs: Any) -> dict[str, Any]:
        return self._record_event(GeopoliticsActionType.DIPLOMATIC_ENGAGEMENT, actor_id, content, kwargs)

    async def strategic_observation(self, actor_id: str, content: str = "", **kwargs: Any) -> dict[str, Any]:
        return self._record_event(GeopoliticsActionType.STRATEGIC_OBSERVATION, actor_id, content, kwargs)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _record_event(
        self,
        action_type: GeopoliticsActionType,
        actor_id: str,
        content: str,
        extra: dict[str, Any],
    ) -> dict[str, Any]:
        event = {
            "action_type": action_type.value,
            "actor_id": actor_id,
            "content": content,
            "label": GEOPOLITICS_ACTION_LABELS_EXTENDED.get(action_type.value, action_type.value),
            "round": self._round,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "target_actor_ids": extra.get("target_actor_ids", []),
            "magnitude": extra.get("magnitude", 0.5),
        }
        self._events.append(event)
        if self._event_callback:
            try:
                self._event_callback(event)
            except Exception as e:
                logger.warning("Event callback failed: %s", e)
        return event
