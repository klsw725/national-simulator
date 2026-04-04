from __future__ import annotations

import json
import logging

from app.graph.state import SimulationState
from app.llm import llm_chat
from app.prompts.actor_system import REPORT_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


async def generate_report_node(state: SimulationState) -> dict:
    history_lines = []
    for action in state["action_history"][-50:]:
        history_lines.append(
            f"R{action.get('round', '?')} {action.get('actor', '?')}: "
            f"{action.get('action_type', '?')} → {action.get('target', '?')} "
            f"({action.get('intensity', '?')}) - {action.get('reasoning', '')}"
        )

    tension_text = json.dumps(state.get("tension_levels", {}), ensure_ascii=False)
    user_prompt = (
        f"## 시나리오\n{state['situation_summary'][:1500]}\n\n"
        f"## 시뮬레이션 이력 ({state['current_round']}라운드)\n"
        + "\n".join(history_lines)
        + f"\n\n## 최종 긴장도\n{tension_text}"
    )

    try:
        report = await llm_chat(
            system=REPORT_SYSTEM_PROMPT,
            user=user_prompt,
            temperature=0.5,
            max_tokens=4000,
        )
    except Exception:
        logger.exception("Report generation failed")
        report = f"[보고서 생성 실패] {state['current_round']}라운드 완료."

    return {
        "phase": "reporting",
        "status": "completed",
        "situation_summary": report,
    }
