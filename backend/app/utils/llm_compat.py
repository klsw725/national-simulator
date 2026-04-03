"""Reasoning/thinking 모델 호환 헬퍼.

일부 모델(예: QwQ, DeepSeek-R1 계열)은 응답을 message.content 대신
message.reasoning_content 또는 provider_specific_fields에만 넣는다.
이 헬퍼는 가능한 모든 위치에서 텍스트를 추출한다.
"""

from __future__ import annotations

import re
from typing import Any


def extract_content(message: Any) -> str:
    content = getattr(message, "content", None) or ""
    if not content:
        content = getattr(message, "reasoning_content", None) or ""
    if not content:
        pf = getattr(message, "provider_specific_fields", None) or {}
        if isinstance(pf, dict):
            content = pf.get("reasoning_content", "") or pf.get("reasoning", "") or ""
    if not isinstance(content, str):
        content = str(content)
    content = re.sub(r"<think>[\s\S]*?</think>", "", content).strip()
    return content
