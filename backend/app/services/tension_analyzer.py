from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from app.database import get_pool

logger = logging.getLogger(__name__)


class TensionAnalyzer:
    def __init__(self, threshold: float = 0.7):
        self._threshold = threshold

    async def analyze_round(
        self,
        scenario_id: str,
        result_id: str,
        current_round: int,
        actions: list[dict],
    ) -> dict | None:
        if not actions:
            return None

        round_actions = [a for a in actions if a.get("round") == current_round]
        if not round_actions:
            return None

        tension = self._compute_tension(round_actions)

        if tension < self._threshold:
            return None

        logger.info(
            "Tension threshold breached: round=%d tension=%.2f threshold=%.2f",
            current_round, tension, self._threshold,
        )

        dp_id = f"dp_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()

        options = json.dumps([
            {
                "id": "continue",
                "label": "계속 진행",
                "description": "시뮬레이션을 중단 없이 계속합니다.",
                "confidence": 0.5,
                "reasoning": "현재 긴장도가 높지만 시나리오 범위 내입니다.",
                "data": {},
            },
            {
                "id": "pause_and_review",
                "label": "일시정지 + 검토",
                "description": f"라운드 {current_round}에서 일시정지하고 상황을 검토합니다.",
                "confidence": 0.7,
                "reasoning": f"긴장도 {tension:.2f}가 임계치 {self._threshold}를 초과했습니다.",
                "data": {"tension": tension, "round": current_round},
            },
            {
                "id": "inject_deescalation",
                "label": "긴장 완화 이벤트 주입",
                "description": "외교적 긴장 완화 이벤트를 다음 라운드에 주입합니다.",
                "confidence": 0.3,
                "reasoning": "긴장 완화 이벤트가 시나리오 방향을 바꿀 수 있습니다.",
                "data": {"tension": tension, "round": current_round},
            },
        ], ensure_ascii=False)

        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO decision_points (id, scenario_id, type, options, recommended, allow_custom, status, created_at)
                   VALUES ($1, $2, 'tension_alert', $3, 'pause_and_review', TRUE, 'pending', $4)""",
                dp_id, scenario_id, options, now,
            )

        return {
            "decision_point_id": dp_id,
            "tension": tension,
            "round": current_round,
            "action_count": len(round_actions),
        }

    def _compute_tension(self, actions: list[dict]) -> float:
        if not actions:
            return 0.0

        tension_signals = 0
        total_signals = 0

        for action in actions:
            content = (action.get("content") or action.get("text") or "").lower()
            action_type = (action.get("action_type") or action.get("type") or "").lower()

            total_signals += 1

            if action_type in ("military", "threat", "attack", "sanction", "blockade"):
                tension_signals += 1
            elif any(kw in content for kw in ("전쟁", "공격", "위협", "제재", "봉쇄", "war", "attack", "threat", "sanction")):
                tension_signals += 1

        if total_signals == 0:
            return 0.0

        return round(tension_signals / total_signals, 2)
