"""
LLM 클라이언트 캡슐화
OpenAI 형식을 사용하여 호출 통합
"""

import json
import re
from typing import Optional, Dict, Any, List
from openai import OpenAI

from ..config import Config


class LLMClient:
    """LLM 클라이언트"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.api_key = api_key or Config.LLM_API_KEY
        self.base_url = base_url or Config.LLM_BASE_URL
        self.model = model or Config.LLM_MODEL_NAME

        if not self.api_key:
            raise ValueError("LLM_API_KEY가 설정되지 않았습니다")

        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: Optional[Dict] = None,
    ) -> str:
        """
        채팅 요청 전송

        Args:
            messages: 메시지 목록
            temperature: 온도 파라미터
            max_tokens: 최대 토큰 수
            response_format: 응답 형식 (예: JSON 모드)

        Returns:
            모델 응답 텍스트
        """
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "extra_body": {"chat_template_kwargs": {"enable_thinking": False}},
        }

        if response_format:
            kwargs["response_format"] = response_format

        response = self.client.chat.completions.create(**kwargs)
        msg = response.choices[0].message
        content = msg.content or ""
        if not content:
            content = getattr(msg, "reasoning_content", "") or ""
            if not content:
                pf = getattr(msg, "provider_specific_fields", None) or {}
                content = pf.get("reasoning_content", "") or pf.get("reasoning", "") or ""
        content = re.sub(r"<think>[\s\S]*?</think>", "", content).strip()
        return content

    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> Dict[str, Any]:
        """
        채팅 요청을 전송하고 JSON 반환

        Args:
            messages: 메시지 목록
            temperature: 온도 파라미터
            max_tokens: 최대 토큰 수

        Returns:
            파싱된 JSON 객체
        """
        response = self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        # Markdown 코드 블록 마크업 정리
        cleaned_response = response.strip()
        cleaned_response = re.sub(
            r"^```(?:json)?\s*\n?", "", cleaned_response, flags=re.IGNORECASE
        )
        cleaned_response = re.sub(r"\n?```\s*$", "", cleaned_response)
        cleaned_response = cleaned_response.strip()

        try:
            return json.loads(cleaned_response)
        except json.JSONDecodeError:
            raise ValueError(
                f"LLM이 반환한 JSON 형식이 유효하지 않음: {cleaned_response}"
            )
