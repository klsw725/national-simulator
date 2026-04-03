from __future__ import annotations

import logging
import uuid
from typing import Any

from openai import AsyncOpenAI

from app.config import settings
from app.services.copilot_context import CopilotContextBuilder

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
당신은 OSINT 시뮬레이션 분석 코파일럿입니다.
분석관의 질문에 정확하고 간결하게 답하세요.

규칙:
- 아래 제공된 데이터에 근거한 답변만 하세요. 추측하지 마세요.
- 데이터가 없으면 "해당 데이터가 없습니다"라고 명확히 말하세요.
- 숫자를 제시할 때는 출처(관측, 시뮬레이션 결과, 지정학 이벤트 등)를 명시하세요.
- 한국어로 답변하세요.

현재 시나리오 데이터:
{context}
"""


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

        response = await self._llm.chat.completions.create(
            model=settings.llm_model_name,
            messages=history,
            temperature=0.3,
            max_tokens=2048,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        )

        choice = response.choices[0]
        from app.utils.llm_compat import extract_content

        assistant_content = extract_content(choice.message)

        history.append({"role": "assistant", "content": assistant_content})

        if len(history) > 40:
            system_msg = history[0]
            self._conversations[conversation_id] = [system_msg] + history[-20:]

        suggestions = self._generate_suggestions(message)

        return {
            "response": assistant_content,
            "conversation_id": conversation_id,
            "sources": ["scenario_context"],
            "tools_used": [],
            "suggestions": suggestions,
        }

    def _generate_suggestions(self, message: str) -> list[str]:
        base = [
            "이 시나리오의 핵심 발견을 요약해줘",
            "가장 공격적인 행위자는 누구인가?",
            "지정학 이벤트 분포를 분석해줘",
            "긴장이 가장 고조된 라운드를 분석해줘",
            "관측된 자산의 국가별 분포를 알려줘",
            "군사훈련이 긴장도에 미치는 인과적 영향은?",
            "제재가 없었다면 결과가 어떻게 달랐을까?",
        ]
        return [s for s in base if s not in message][:3]
