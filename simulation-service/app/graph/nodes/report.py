from __future__ import annotations

import json
import logging

from app.graph.state import SimulationState
from app.llm import llm_chat
from app.prompts.actor_system import REPORT_SYSTEM_PROMPT
from app.services.event_emitter import get_emitter

logger = logging.getLogger(__name__)


def _build_graph_context(state: SimulationState) -> str:
    engine = state.get("decision_engine_state", {})
    entities = engine.get("extracted_entities", [])
    relations = engine.get("extracted_relations", [])
    if not entities:
        return ""

    lines = ["## 엔티티 관계 그래프"]

    by_type: dict[str, list[str]] = {}
    for e in entities:
        t = e.get("type", "Entity")
        by_type.setdefault(t, []).append(e.get("name") or e.get("id", "?"))
    for t, names in by_type.items():
        lines.append(f"- {t}: {', '.join(names)}")

    if relations:
        lines.append("")
        lines.append("### 주요 관계")
        for r in relations[:30]:
            strength = r.get("strength", "")
            strength_str = f" (강도 {strength})" if strength else ""
            lines.append(
                f"- {r.get('source', '?')} —[{r.get('type', '?')}]→ "
                f"{r.get('target', '?')}{strength_str}"
            )

    return "\n".join(lines)


async def generate_report_node(state: SimulationState) -> dict:
    history_lines = []
    for action in state["action_history"][-50:]:
        history_lines.append(
            f"R{action.get('round', '?')} {action.get('actor', '?')}: "
            f"{action.get('action_type', '?')} → {action.get('target', '?')} "
            f"({action.get('intensity', '?')}) - {action.get('reasoning', '')}"
        )

    tension_text = json.dumps(state.get("tension_levels", {}), ensure_ascii=False)
    graph_context = _build_graph_context(state)
    user_prompt = (
        f"## 시나리오\n{state['situation_summary'][:1500]}\n\n"
        + (f"{graph_context}\n\n" if graph_context else "")
        + f"## 시뮬레이션 이력 ({state['current_round']}라운드)\n"
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

    try:
        await get_emitter().emit_phase_change(state["scenario_id"], "reporting", 0.9)
        await get_emitter().emit_report_ready(state["scenario_id"], state["scenario_id"])
    except Exception:
        pass

    return {
        "phase": "reporting",
        "status": "completed",
        "situation_summary": report,
    }
