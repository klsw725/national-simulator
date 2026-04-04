from __future__ import annotations

import json
import re
from typing import Any

from openai import AsyncOpenAI

from app.config import settings

_client: AsyncOpenAI | None = None


def get_llm_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )
    return _client


async def llm_chat(
    system: str,
    user: str,
    *,
    temperature: float = 0.7,
    max_tokens: int = 2000,
) -> str:
    client = get_llm_client()
    resp = await client.chat.completions.create(
        model=settings.llm_model_name,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    content = resp.choices[0].message.content or ""
    content = re.sub(r"<think>[\s\S]*?</think>", "", content).strip()
    return content


def _extract_json(raw: str) -> Any:
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if match:
        return json.loads(match.group(1).strip())

    for start_char, end_char in [("[", "]"), ("{", "}")]:
        first = raw.find(start_char)
        if first == -1:
            continue
        depth = 0
        for i in range(first, len(raw)):
            if raw[i] == start_char:
                depth += 1
            elif raw[i] == end_char:
                depth -= 1
            if depth == 0:
                return json.loads(raw[first : i + 1])

    raise ValueError(f"No JSON found in LLM response: {raw[:300]}")


async def llm_json(
    system: str,
    user: str,
    *,
    temperature: float = 0.3,
    max_tokens: int = 3000,
) -> Any:
    raw = await llm_chat(system, user, temperature=temperature, max_tokens=max_tokens)
    return _extract_json(raw)
