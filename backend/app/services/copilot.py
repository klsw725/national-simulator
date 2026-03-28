from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from openai import AsyncOpenAI

from app.config import settings
from app.services.copilot_context import CopilotContextBuilder
from app.services.copilot_tools import TOOL_DEFINITIONS, execute_tool

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
당신은 OSINT 시뮬레이션 분석 코파일럿입니다.
분석관의 질문에 정확하고 간결하게 답하세요.

규칙:
- 데이터에 근거한 답변만 하세요. 추측하지 마세요.
- 도구를 사용하여 실제 데이터를 검색/분석한 후 답변하세요.
- 데이터가 없으면 "해당 데이터가 없습니다"라고 명확히 말하세요.
- 숫자를 제시할 때는 출처(관측, 시뮬레이션 결과, 지정학 이벤트 등)를 명시하세요.
- 한국어로 답변하세요.

현재 시나리오 컨텍스트:
{context}
"""

MAX_TOOL_ROUNDS = 5


class CopilotService:
    def __init__(self):
        self._llm = AsyncOpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )
        self._context_builder = CopilotContextBuilder()
        self._conversations: dict[str, list[dict[str, Any]]] = {}

    async def chat(
        self,
        scenario_id: str,
        message: str,
        conversation_id: str | None = None,
    ) -> dict[str, Any]:
        if not conversation_id:
            conversation_id = f"conv_{uuid.uuid4().hex[:12]}"

        context = await self._context_builder.build(scenario_id)

        if conversation_id not in self._conversations:
            self._conversations[conversation_id] = [
                {"role": "system", "content": SYSTEM_PROMPT.format(context=context)},
            ]

        history = self._conversations[conversation_id]
        history.append({"role": "user", "content": message})

        tools_used: list[str] = []
        sources: list[str] = []

        for _ in range(MAX_TOOL_ROUNDS):
            try:
                response = await self._llm.chat.completions.create(
                    model=settings.llm_model_name,
                    messages=history,
                    tools=TOOL_DEFINITIONS,
                    temperature=0.3,
                    max_tokens=2048,
                    extra_body={"chat_template_kwargs": {"enable_thinking": False}},
                )
            except Exception:
                logger.warning("LLM tool-calling failed, retrying without tools")
                response = await self._llm.chat.completions.create(
                    model=settings.llm_model_name,
                    messages=history,
                    temperature=0.3,
                    max_tokens=2048,
                    extra_body={"chat_template_kwargs": {"enable_thinking": False}},
                )

            choice = response.choices[0]

            if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
                msg = {"role": "assistant", "content": choice.message.content or ""}
                msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in choice.message.tool_calls
                ]
                history.append(msg)

                for tool_call in choice.message.tool_calls:
                    fn_name = tool_call.function.name
                    fn_args = json.loads(tool_call.function.arguments)

                    if "scenario_id" not in fn_args:
                        fn_args["scenario_id"] = scenario_id

                    tool_result = await execute_tool(fn_name, fn_args)
                    tools_used.append(fn_name)

                    parsed = json.loads(tool_result)
                    if isinstance(parsed, dict):
                        for key in ("observations", "by_source", "by_actor", "top_actors"):
                            if key in parsed:
                                sources.append(f"tool:{fn_name}")
                                break

                    history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": tool_result,
                    })

                continue

            assistant_content = choice.message.content or ""
            history.append({"role": "assistant", "content": assistant_content})

            if len(history) > 40:
                system_msg = history[0]
                self._conversations[conversation_id] = [system_msg] + history[-20:]

            suggestions = self._generate_suggestions(message, tools_used)

            return {
                "response": assistant_content,
                "conversation_id": conversation_id,
                "sources": list(set(sources)),
                "tools_used": list(set(tools_used)),
                "suggestions": suggestions,
            }

        last_content = history[-1].get("content", "") if history else ""
        return {
            "response": last_content or "도구 호출 제한에 도달했습니다.",
            "conversation_id": conversation_id,
            "sources": list(set(sources)),
            "tools_used": list(set(tools_used)),
            "suggestions": [],
        }

    def _generate_suggestions(self, message: str, tools_used: list[str]) -> list[str]:
        suggestions: list[str] = []

        if "search_observations" in tools_used:
            suggestions.append("이 자산들의 국가별 분포를 분석해줘")
        if "analyze_simulation_actions" in tools_used:
            suggestions.append("가장 활발한 행위자의 행동 패턴을 분석해줘")
        if "get_geopolitics_summary" in tools_used:
            suggestions.append("긴장이 가장 고조된 라운드를 분석해줘")

        if not suggestions:
            suggestions = [
                "이 시나리오의 핵심 발견을 요약해줘",
                "가장 공격적인 행위자는 누구인가?",
                "지정학 이벤트 분포를 분석해줘",
            ]

        return suggestions[:3]
