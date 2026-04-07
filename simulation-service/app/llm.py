from __future__ import annotations

import json
import logging
import re
from typing import Any

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)

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


def _sanitize_json_string(s: str) -> str:
    s = re.sub(r"//[^\n]*", "", s)
    s = re.sub(r",\s*([}\]])", r"\1", s)
    return s


def _try_parse(s: str) -> Any:
    try:
        return json.loads(s)
    except (json.JSONDecodeError, ValueError):
        pass
    return json.loads(_sanitize_json_string(s))


def _extract_json(raw: str) -> Any:
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if match:
        try:
            return _try_parse(match.group(1).strip())
        except (json.JSONDecodeError, ValueError):
            pass

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
                try:
                    return _try_parse(raw[first : i + 1])
                except (json.JSONDecodeError, ValueError):
                    break

    raise ValueError(f"No valid JSON found in LLM response: {raw[:300]}")


async def llm_json(
    system: str,
    user: str,
    *,
    temperature: float = 0.3,
    max_tokens: int = 3000,
    retries: int = 1,
) -> Any:
    last_exc: Exception | None = None
    for attempt in range(1 + retries):
        try:
            raw = await llm_chat(system, user, temperature=temperature, max_tokens=max_tokens)
            return _extract_json(raw)
        except (json.JSONDecodeError, ValueError) as exc:
            last_exc = exc
            if attempt < retries:
                logger.warning("llm_json parse failed (attempt %d), retrying: %s", attempt + 1, str(exc)[:200])
    raise last_exc  # type: ignore[misc]
