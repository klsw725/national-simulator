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


async def llm_json(
    system: str,
    user: str,
    *,
    temperature: float = 0.3,
    max_tokens: int = 3000,
) -> Any:
    raw = await llm_chat(system, user, temperature=temperature, max_tokens=max_tokens)
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    text = match.group(1).strip() if match else raw.strip()
    if text.startswith("[") or text.startswith("{"):
        return json.loads(text)
    raise ValueError(f"Failed to parse JSON from LLM response: {text[:200]}")
