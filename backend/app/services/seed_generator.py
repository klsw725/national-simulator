"""시드 문서 생성 서비스.

ShadowBroker OSINT 데이터를 기반으로 MiroFish에 전달할
자연어 시드 문서(마크다운)를 생성한다.

흐름: SB API → 군함 식별/매핑 → GDELT 컨텍스트 → LLM 시드 문서 생성
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from openai import AsyncOpenAI

from app.clients.shadowbroker import BBox, ShadowBrokerClient
from app.config import settings
from app.services.gdelt_extractor import extract_gdelt_context, format_gdelt_text
from app.services.vessel_mapper import VesselMapper

logger = logging.getLogger(__name__)

SEED_GENERATION_PROMPT = """\
당신은 지정학적 분석가입니다. 아래 OSINT 데이터를 기반으로
시뮬레이션 시드 문서를 마크다운으로 작성해 주세요.

## 군함 배치 현황
{vessel_deployment}

## GDELT 분쟁 이벤트 (최근)
{gdelt_context}

## 시뮬레이션 질문
{user_question}

## 해역 정보
{region_name}

다음 형식으로 작성하세요:
1. **현재 상황 요약** (200자 이내) — 해역의 군사적 긴장 상황 개요
2. **주요 행위자와 그 입장** — 각 국가의 군사력 배치와 외교적 입장
3. **긴장 요인 및 잠재적 충돌 시나리오** — 구체적 대립 요인
4. **각 행위자의 예상 반응 경로** — 외교적/군사적 반응 시나리오

시드 문서는 약 2000자 이내로 작성하세요.
각 행위자(국가)는 이후 소셜미디어 시뮬레이션에서 개별 에이전트로 동작합니다.
실제 OSINT 데이터에 기반하여 현실적으로 작성하세요.
"""


class SeedGenerator:
    def __init__(
        self,
        sb_client: ShadowBrokerClient,
        vessel_mapper: VesselMapper | None = None,
    ):
        self.sb = sb_client
        self.mapper = vessel_mapper or VesselMapper()
        self._llm = AsyncOpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )

    async def generate(
        self,
        bbox: list[float],
        question: str,
        region_name: str = "",
    ) -> dict[str, Any]:
        """시드 문서 생성.

        Args:
            bbox: [min_lng, min_lat, max_lng, max_lat]
            question: 사용자의 시뮬레이션 질문
            region_name: 해역 이름 (예: "South China Sea")

        Returns:
            {"text": str, "metadata": dict}
        """
        sb_bbox = BBox(s=bbox[1], w=bbox[0], n=bbox[3], e=bbox[2])

        # 1. SB에서 선박 + GDELT 데이터 조회
        ships = await self.sb.get_ships(sb_bbox)
        gdelt_data = await self.sb.get_gdelt(sb_bbox)

        # 2. 군함 식별 + 국가 매핑
        military_vessels = self.mapper.identify_military_vessels(ships)
        actors = self.mapper.map_to_actors(military_vessels)

        # 3. GDELT 컨텍스트 추출
        gdelt_context = extract_gdelt_context(gdelt_data, bbox)

        # 4. LLM 프롬프트 구성 + 시드 문서 생성
        vessel_text = self.mapper.format_deployment_text(actors)
        gdelt_text = format_gdelt_text(gdelt_context)

        prompt = SEED_GENERATION_PROMPT.format(
            vessel_deployment=vessel_text,
            gdelt_context=gdelt_text,
            user_question=question,
            region_name=region_name or "미지정",
        )

        seed_text = await self._call_llm(prompt)

        # 5. 메타데이터 구성
        metadata = {
            "vessels_count": len(military_vessels),
            "actors_identified": list(actors.keys()),
            "gdelt_events_count": gdelt_context["event_count"],
            "tension_score": gdelt_context["tension_score"],
            "data_timestamp": datetime.now(timezone.utc).isoformat(),
        }

        logger.info(
            "Seed generated: %d vessels, %d actors, tension=%.1f",
            metadata["vessels_count"],
            len(metadata["actors_identified"]),
            metadata["tension_score"],
        )

        return {"text": seed_text, "metadata": metadata}

    async def _call_llm(self, prompt: str) -> str:
        """OpenAI Compatible API로 시드 문서 생성."""
        response = await self._llm.chat.completions.create(
            model=settings.llm_model_name,
            messages=[
                {
                    "role": "system",
                    "content": "당신은 지정학적 분석 전문가입니다. OSINT 데이터를 기반으로 정확하고 현실적인 분석 문서를 작성합니다.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
            max_tokens=2048,
        )
        return response.choices[0].message.content or ""
