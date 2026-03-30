from __future__ import annotations

import json
import logging
import re
from typing import Any

import pandas as pd
from openai import AsyncOpenAI

from app.causal.models import CausalEdge
from app.config import settings

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """\
주어진 텍스트에서 인과 관계를 추출하세요. 각 관계에 대해:
- cause: 원인 (변수 또는 이벤트)
- effect: 결과 (변수 또는 이벤트)
- relationship: "causes" | "enables" | "prevents"
- confidence: 0.0-1.0 (텍스트에서의 인과 근거 강도)
- evidence: 텍스트에서 인과 관계를 뒷받침하는 인용문

상관 관계는 제외하고 인과 관계만 포함하세요.
"A와 B가 동시에 발생" → 상관 (제외)
"A로 인해 B가 발생" → 인과 (포함)
"A가 B를 가능하게 함" → enables (포함)
"A가 B를 억제함" → prevents (포함)

JSON 배열로만 출력하세요. 다른 텍스트는 포함하지 마세요.
[{"cause": "...", "effect": "...", "relationship": "...", "confidence": 0.0, "evidence": "..."}]
"""


class CausalExtractor:
    def __init__(self):
        self._llm = AsyncOpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )

    async def extract_from_text(
        self,
        text: str,
        existing_variables: list[str] | None = None,
    ) -> list[CausalEdge]:
        user_blocks = [f"분석 텍스트:\n{text}"]
        if existing_variables:
            vars_text = ", ".join(sorted({v.strip() for v in existing_variables if v and v.strip()}))
            if vars_text:
                user_blocks.append(
                    "가능하면 아래 기존 변수명을 source/target으로 우선 매핑하세요:\n"
                    f"{vars_text}",
                )

        response = await self._llm.chat.completions.create(
            model=settings.llm_model_name,
            messages=[
                {"role": "system", "content": EXTRACTION_PROMPT},
                {"role": "user", "content": "\n\n".join(user_blocks)},
            ],
            temperature=0.1,
            max_tokens=2048,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        )

        content = response.choices[0].message.content or ""
        payload = self._parse_json_array(content)
        if payload is None:
            logger.warning("Failed to parse causal extraction response as JSON array")
            return []

        edges: list[CausalEdge] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            source = str(item.get("cause") or "").strip()
            target = str(item.get("effect") or "").strip()
            if not source or not target:
                continue

            relationship = str(item.get("relationship") or "causes").strip().lower()
            if relationship not in {"causes", "enables", "prevents"}:
                relationship = "causes"

            confidence_raw = item.get("confidence")
            confidence: float | None = None
            if isinstance(confidence_raw, (int, float)):
                confidence = max(0.0, min(1.0, float(confidence_raw)))

            edges.append(
                CausalEdge(
                    source=source,
                    target=target,
                    edge_type=relationship,
                    confidence=confidence,
                    provenance="llm_extracted",
                ),
            )

        return edges

    async def validate_with_data(
        self,
        candidates: list[CausalEdge],
        df: pd.DataFrame,
    ) -> list[CausalEdge]:
        if len(df) < 30:
            return candidates

        try:
            from pgmpy.estimators.CITests import chi_square
        except ImportError:
            logger.warning("pgmpy not available; skipping statistical causal validation")
            return candidates

        validated: list[CausalEdge] = []

        for edge in candidates:
            source = edge.source
            target = edge.target

            if source not in df.columns or target not in df.columns:
                validated.append(edge.model_copy(update={"provenance": f"{edge.provenance}|unverified"}))
                continue

            test_df = df[[source, target]].dropna().copy()
            if len(test_df) < 30:
                validated.append(edge.model_copy(update={"provenance": f"{edge.provenance}|unverified"}))
                continue

            for col in (source, target):
                if pd.api.types.is_numeric_dtype(test_df[col]):
                    unique_count = int(test_df[col].nunique(dropna=True))
                    if unique_count > 10:
                        test_df[col] = pd.qcut(test_df[col], q=4, duplicates="drop").astype(str)
                    else:
                        test_df[col] = test_df[col].round(4).astype(str)
                else:
                    test_df[col] = test_df[col].astype(str)

            try:
                stat_result: Any = chi_square(
                    X=source,
                    Y=target,
                    Z=[],
                    data=test_df,
                    boolean=False,
                )

                p_value: float | None = None
                if isinstance(stat_result, tuple) and len(stat_result) >= 2:
                    p_value = float(stat_result[1])

                if p_value is None:
                    validated.append(edge.model_copy(update={"provenance": f"{edge.provenance}|unverified"}))
                    continue

                if p_value > 0.05:
                    base_conf = edge.confidence if edge.confidence is not None else 0.5
                    weakened = max(0.0, min(1.0, float(base_conf) * 0.5))
                    validated.append(
                        edge.model_copy(
                            update={
                                "confidence": weakened,
                                "provenance": f"{edge.provenance}|stat_not_rejected",
                            },
                        ),
                    )
                else:
                    validated.append(edge.model_copy(update={"provenance": f"{edge.provenance}|stat_supported"}))
            except Exception:
                logger.warning("Failed chi-square validation for edge %s -> %s", source, target)
                validated.append(edge.model_copy(update={"provenance": f"{edge.provenance}|unverified"}))

        return validated

    async def extract_and_validate(
        self,
        text: str,
        df: pd.DataFrame | None = None,
    ) -> list[CausalEdge]:
        candidates = await self.extract_from_text(text)
        if df is not None and len(df) >= 30:
            candidates = await self.validate_with_data(candidates, df)
        return candidates

    def _parse_json_array(self, content: str) -> list[dict[str, Any]] | None:
        content = content.strip()
        direct = self._load_if_array(content)
        if direct is not None:
            return direct

        code_block_matches = re.findall(r"```json\s*(.*?)\s*```", content, flags=re.IGNORECASE | re.DOTALL)
        for block in code_block_matches:
            parsed = self._load_if_array(block.strip())
            if parsed is not None:
                return parsed

        left = content.find("[")
        right = content.rfind("]")
        if left != -1 and right != -1 and left < right:
            parsed = self._load_if_array(content[left:right + 1])
            if parsed is not None:
                return parsed

        return None

    @staticmethod
    def _load_if_array(raw: str) -> list[dict[str, Any]] | None:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        return None
