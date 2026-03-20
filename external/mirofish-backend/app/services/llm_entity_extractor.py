import json
import uuid as uuid_mod
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable

from ..config import Config
from ..utils.logger import get_logger
from ..utils.llm_client import LLMClient

logger = get_logger("mirofish.llm_entity_extractor")


@dataclass
class ExtractedEntity:
    name: str
    type: str
    summary: str
    attributes: Dict[str, Any] = field(default_factory=dict)
    uuid: str = field(default_factory=lambda: uuid_mod.uuid4().hex[:16])


@dataclass
class ExtractedRelationship:
    source: str
    target: str
    type: str
    fact: str
    uuid: str = field(default_factory=lambda: uuid_mod.uuid4().hex[:16])


@dataclass
class ExtractionResult:
    entities: List[ExtractedEntity]
    relationships: List[ExtractedRelationship]
    source_text: str


class LLMEntityExtractor:
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self._llm_client = llm_client

    @property
    def llm(self) -> LLMClient:
        if self._llm_client is None:
            self._llm_client = LLMClient()
        return self._llm_client

    def build_system_prompt(
        self, ontology: Dict, existing_entities: Optional[List[str]] = None
    ) -> str:
        entity_types_desc = []
        for et in ontology.get("entity_types", []):
            attrs = ", ".join(
                f"{a['name']}({a.get('description', '')})"
                for a in et.get("attributes", [])
            )
            line = f"- {et['name']}: {et.get('description', '')}"
            if attrs:
                line += f"\n  속성: {attrs}"
            entity_types_desc.append(line)

        edge_types_desc = []
        for edge in ontology.get("edge_types", []):
            targets = ", ".join(
                f"{st.get('source', '?')} → {st.get('target', '?')}"
                for st in edge.get("source_targets", [])
            )
            line = f"- {edge['name']}: {edge.get('description', '')}"
            if targets:
                line += f"\n  연결: {targets}"
            edge_types_desc.append(line)

        existing_note = ""
        if existing_entities:
            existing_note = (
                f"\n5. 이미 알려진 엔티티: {', '.join(existing_entities[:50])}. "
                "동일 대상이면 같은 이름을 사용하세요."
            )

        return (
            "당신은 지식 그래프 구축 전문가입니다. 주어진 텍스트에서 엔티티와 관계를 추출합니다.\n\n"
            "### 허용된 엔티티 유형:\n"
            f"{''.join(entity_types_desc) if entity_types_desc else '(제한 없음)'}\n\n"
            "### 허용된 관계 유형:\n"
            f"{''.join(edge_types_desc) if edge_types_desc else '(제한 없음)'}\n\n"
            "### 규칙:\n"
            "1. 위에 정의된 유형만 사용하세요\n"
            "2. 엔티티 이름은 정규화하세요 (동일 대상의 다른 호칭은 하나로 통일)\n"
            "3. fact는 원문에서 유래하는 구체적 사실이어야 합니다\n"
            "4. 텍스트에 명시적으로 언급된 정보만 추출하세요"
            f"{existing_note}\n\n"
            "### JSON 출력 형식:\n"
            "{\n"
            '  "entities": [\n'
            '    {"name": "엔티티 이름", "type": "엔티티 유형", "summary": "한줄 요약", "attributes": {"속성명": "값"}}\n'
            "  ],\n"
            '  "relationships": [\n'
            '    {"source": "소스 엔티티 이름", "target": "타겟 엔티티 이름", "type": "관계 유형", "fact": "사실 설명"}\n'
            "  ]\n"
            "}"
        )

    def extract_from_chunk(
        self,
        chunk: str,
        ontology: Dict,
        existing_entities: Optional[List[str]] = None,
    ) -> ExtractionResult:
        system_prompt = self.build_system_prompt(ontology, existing_entities)
        user_prompt = f"다음 텍스트에서 엔티티와 관계를 추출하세요:\n\n{chunk}"

        try:
            raw = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
            )
        except Exception as exc:
            logger.warning(f"LLM 추출 실패: {str(exc)[:200]}")
            return ExtractionResult(entities=[], relationships=[], source_text=chunk)

        entities, relationships = self._validate_extraction(raw, ontology)
        return ExtractionResult(
            entities=entities, relationships=relationships, source_text=chunk
        )

    def extract_from_chunks(
        self,
        chunks: List[str],
        ontology: Dict,
        progress_callback: Optional[Callable] = None,
    ) -> List[ExtractionResult]:
        results: List[ExtractionResult] = []
        known_entities: List[str] = []

        for i, chunk in enumerate(chunks):
            if progress_callback:
                progress_callback(
                    f"엔티티 추출 중... ({i + 1}/{len(chunks)})",
                    (i + 1) / len(chunks),
                )

            result = self.extract_from_chunk(chunk, ontology, known_entities)
            results.append(result)

            for entity in result.entities:
                if entity.name not in known_entities:
                    known_entities.append(entity.name)

            logger.debug(
                f"청크 {i + 1}/{len(chunks)}: "
                f"{len(result.entities)}개 엔티티, {len(result.relationships)}개 관계 추출"
            )

        total_e = sum(len(r.entities) for r in results)
        total_r = sum(len(r.relationships) for r in results)
        logger.info(
            f"추출 완료: {len(chunks)}개 청크에서 {total_e}개 엔티티, {total_r}개 관계"
        )
        return results

    def _validate_extraction(self, raw: Dict, ontology: Dict) -> tuple:
        valid_entity_types = {et["name"] for et in ontology.get("entity_types", [])}
        valid_edge_types = {et["name"] for et in ontology.get("edge_types", [])}

        entities: List[ExtractedEntity] = []
        for item in raw.get("entities", []):
            if not isinstance(item, dict):
                continue
            name = item.get("name", "").strip()
            etype = item.get("type", "").strip()
            if not name:
                continue
            if valid_entity_types and etype not in valid_entity_types:
                logger.debug(f"온톨로지에 없는 엔티티 타입 필터링: {etype} ({name})")
                continue
            entities.append(
                ExtractedEntity(
                    name=name,
                    type=etype,
                    summary=item.get("summary", ""),
                    attributes=item.get("attributes", {}),
                )
            )

        relationships: List[ExtractedRelationship] = []
        for item in raw.get("relationships", []):
            if not isinstance(item, dict):
                continue
            source = item.get("source", "").strip()
            target = item.get("target", "").strip()
            rtype = item.get("type", "").strip()
            fact = item.get("fact", "").strip()
            if not source or not target:
                continue
            if valid_edge_types and rtype not in valid_edge_types:
                logger.debug(f"온톨로지에 없는 관계 타입 필터링: {rtype}")
                continue
            relationships.append(
                ExtractedRelationship(
                    source=source, target=target, type=rtype, fact=fact
                )
            )

        return entities, relationships
