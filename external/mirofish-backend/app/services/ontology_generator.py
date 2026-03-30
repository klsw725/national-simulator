"""
온톨로지 생성 서비스
인터페이스 1: 텍스트 내용을 분석하여 사회 시뮬레이션에 적합한 엔티티 및 관계 유형 정의 생성
"""

import json
from typing import Dict, Any, List, Optional
from ..utils.llm_client import LLMClient


# 온톨로지 생성을 위한 시스템 프롬프트
ONTOLOGY_SYSTEM_PROMPT = """당신은 전문적인 지식 그래프 온톨로지 설계 전문가입니다. 당신의 임무는 주어진 텍스트 내용과 시뮬레이션 요구사항을 분석하여 **소셜 미디어 여론 시뮬레이션**에 적합한 엔티티 유형과 관계 유형을 설계하는 것입니다.

**중요: 반드시 유효한 JSON 형식의 데이터를 출력해야 하며, 다른 어떤 내용도 출력해서는 안 됩니다.**

## 핵심 작업 배경

우리는 **소셜 미디어 여론 시뮬레이션 시스템**을 구축하고 있습니다. 이 시스템에서:
- 각 엔티티는 소셜 미디어에서 발언하고, 상호작용하며, 정보를 전파할 수 있는 "계정" 또는 "주체"입니다.
- 엔티티 간에는 서로 영향을 주고받으며, 리포스트(전달), 댓글, 응답 등의 활동을 합니다.
- 우리는 여론 사건에서 각 측의 반응과 정보 전파 경로를 시뮬레이션해야 합니다.

따라서, **엔티티는 현실 세계에 실제로 존재하며 소셜 미디어에서 발언하고 상호작용할 수 있는 주체여야 합니다**:

**가능한 예**:
- 구체적인 개인 (공인, 당사자, 오피니언 리더, 전문가/학자, 일반인)
- 회사, 기업 (공식 계정 포함)
- 조직 및 기관 (대학교, 협회, NGO, 노동조합 등)
- 정부 부처, 규제 기관
- 미디어 기관 (신문사, 방송국, 1인 미디어, 웹사이트)
- 소셜 미디어 플랫폼 자체
- 특정 집단 대표 (동문회, 팬클럽, 권익 보호 단체 등)

**불가능한 예**:
- 추상적인 개념 (예: "여론", "정서", "추세")
- 주제/화제 (예: "학술적 정직성", "교육 개혁")
- 관점/태도 (예: "찬성 측", "반대 측")

## 출력 형식

다음 구조를 포함하는 JSON 형식을 출력해 주세요:

```json
{
    "entity_types": [
        {
            "name": "엔티티 유형 이름 (영문, PascalCase)",
            "description": "짧은 설명 (영문, 100자 이내)",
            "attributes": [
                {
                    "name": "속성 이름 (영문, snake_case)",
                    "type": "text",
                    "description": "속성 설명"
                }
            ],
            "examples": ["예시 엔티티 1", "예시 엔티티 2"]
        }
    ],
    "edge_types": [
        {
            "name": "관계 유형 이름 (영문, UPPER_SNAKE_CASE)",
            "description": "짧은 설명 (영문, 100자 이내)",
            "source_targets": [
                {"source": "소스 엔티티 유형", "target": "타겟 엔티티 유형"}
            ],
            "attributes": []
        }
    ],
    "analysis_summary": "텍스트 내용에 대한 간략한 분석 설명 (한국어)"
}
```

## 설계 가이드 (매우 중요!)

### 1. 엔티티 유형 설계 - 엄격히 준수해야 함

**수량 요구사항: 반드시 정확히 10개의 엔티티 유형을 출력해야 함**

**계층 구조 요구사항 (구체적 유형과 범용 유형을 모두 포함해야 함)**:

당신의 10개 엔티티 유형은 다음 계층을 포함해야 합니다:

A. **범용 유형 (반드시 포함, 리스트의 마지막 2개에 배치)**:
   - `Person`: 모든 개인을 위한 범용 유형입니다. 특정 인물이 다른 구체적인 인물 유형에 해당하지 않을 때 이 유형으로 분류합니다.
   - `Organization`: 모든 조직 및 기관을 위한 범용 유형입니다. 특정 조직이 다른 구체적인 조직 유형에 해당하지 않을 때 이 유형으로 분류합니다.

B. **구체적 유형 (8개, 텍스트 내용에 따라 설계)**:
   - 텍스트에 등장하는 주요 역할에 맞춰 더 구체적인 유형을 설계합니다.
   - 예: 학술 관련 사건인 경우 `Student`, `Professor`, `University` 등이 포함될 수 있습니다.
   - 예: 비즈니스 관련 사건인 경우 `Company`, `CEO`, `Employee` 등이 포함될 수 있습니다.

**범용 유형이 필요한 이유**:
- 텍스트에는 "초중고 교사", "행인 A", "어떤 네티즌" 등 다양한 인물이 등장합니다.
- 전용 유형이 없는 경우 이들은 `Person`으로 분류되어야 합니다.
- 마찬가지로 소규모 조직, 임시 단체 등은 `Organization`으로 분류되어야 합니다.

**구체적 유형 설계 원칙**:
- 텍스트에서 빈번하게 등장하거나 핵심적인 역할 유형을 식별합니다.
- 각 구체적 유형은 경계가 명확해야 하며 서로 중복되지 않아야 합니다.
- description은 해당 유형과 범용 유형의 차이점을 명확히 설명해야 합니다.

### 2. 관계 유형 설계

- 수량: 6-10개
- 관계는 소셜 미디어 상호작용에서의 실제 연결을 반영해야 합니다.
- 관계의 source_targets가 당신이 정의한 엔티티 유형들을 포괄하도록 합니다.

### 3. 속성 설계

- 각 엔티티 유형별로 1-3개의 핵심 속성을 정의합니다.
- **주의**: 속성 이름으로 `name`, `uuid`, `group_id`, `created_at`, `summary`를 사용할 수 없습니다 (시스템 예약어).
- 권장 속성명: `full_name`, `title`, `role`, `position`, `location`, `description` 등

## 엔티티 유형 참고

**개인류 (구체적)**:
- Student: 학생
- Professor: 교수/학자
- Journalist: 기자
- Celebrity: 연예인/인플루언서
- Executive: 임원/경영진
- Official: 정부 관료
- Lawyer: 변호사
- Doctor: 의사

**개인류 (범용)**:
- Person: 모든 자연인 (위의 구체적 유형에 해당하지 않을 때 사용)

**조직류 (구체적)**:
- University: 대학교
- Company: 기업/회사
- GovernmentAgency: 정부 기관
- MediaOutlet: 미디어 기관
- Hospital: 병원
- School: 초중고교
- NGO: 비정부 기구

**조직류 (범용)**:
- Organization: 모든 조직 및 기관 (위의 구체적 유형에 해당하지 않을 때 사용)

## 관계 유형 참고

- WORKS_FOR: ~에서 근무함
- STUDIES_AT: ~에서 수학함
- AFFILIATED_WITH: ~에 소속됨
- REPRESENTS: ~를 대표함
- REGULATES: ~를 규제함
- REPORTS_ON: ~에 대해 보도함
- COMMENTS_ON: ~에 대해 논평함
- RESPONDS_TO: ~에 응답함
- SUPPORTS: ~를 지지함
- OPPOSES: ~에 반대함
- COLLABORATES_WITH: ~와 협력함
- COMPETES_WITH: ~와 경쟁함

## 인과 관계 엣지 타입 (필수 포함)

edge_types 목록에 다음 인과 관계 유형을 반드시 포함하세요:
- CAUSES: A가 직접적으로 B를 야기함 (예: 군사 도발이 긴장 고조를 야기)
- ENABLES: A가 B를 가능하게 함 (예: 동맹 관계가 군사 접근을 가능하게 함)
- PREVENTS: A가 B를 억제하거나 방지함 (예: 외교 협상이 군사 충돌을 방지)

이 인과 엣지 타입은 도메인 특화 관계 유형(SUPPORTS, OPPOSES 등)과 함께 포함하세요.
"""


class OntologyGenerator:
    """
    온톨로지 생성기
    텍스트 내용을 분석하여 엔티티 및 관계 유형 정의 생성
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()

    def generate(
        self,
        document_texts: List[str],
        simulation_requirement: str,
        additional_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        온톨로지 정의 생성

        Args:
            document_texts: 문서 텍스트 리스트
            simulation_requirement: 시뮬레이션 요구사항 설명
            additional_context: 추가 컨텍스트

        Returns:
            온톨로지 정의 (entity_types, edge_types 등)
        """
        # 사용자 메시지 구축
        user_message = self._build_user_message(
            document_texts, simulation_requirement, additional_context
        )

        messages = [
            {"role": "system", "content": ONTOLOGY_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        # LLM 호출
        result = self.llm_client.chat_json(
            messages=messages, temperature=0.3, max_tokens=4096
        )

        # 검증 및 후처리
        result = self._validate_and_process(result)

        return result

    # LLM에 전달할 텍스트 최대 길이 (5만 자)
    MAX_TEXT_LENGTH_FOR_LLM = 50000

    def _build_user_message(
        self,
        document_texts: List[str],
        simulation_requirement: str,
        additional_context: Optional[str],
    ) -> str:
        """사용자 메시지 구축"""

        # 텍스트 병합
        combined_text = "\n\n---\n\n".join(document_texts)
        original_length = len(combined_text)

        # 텍스트가 5만 자를 초과하면 절삭 (LLM 전달용에만 영향, 그래프 구축에는 영향 없음)
        if len(combined_text) > self.MAX_TEXT_LENGTH_FOR_LLM:
            combined_text = combined_text[: self.MAX_TEXT_LENGTH_FOR_LLM]
            combined_text += f"\n\n...(원문은 총 {original_length}자이며, 온톨로지 분석을 위해 앞부분 {self.MAX_TEXT_LENGTH_FOR_LLM}자만 추출되었습니다)..."

        message = f"""## 시뮬레이션 요구사항

{simulation_requirement}

## 문서 내용

{combined_text}
"""

        if additional_context:
            message += f"""
## 추가 설명

{additional_context}
"""

        message += """
위 내용을 바탕으로 사회 여론 시뮬레이션에 적합한 엔티티 유형과 관계 유형을 설계해 주세요.

**반드시 준수해야 할 규칙**:
1. 반드시 정확히 10개의 엔티티 유형을 출력해야 합니다.
2. 마지막 2개는 반드시 범용 유형이어야 합니다: Person (개인 범용) 및 Organization (조직 범용)
3. 앞의 8개는 텍스트 내용에 따라 설계된 구체적인 유형이어야 합니다.
4. 모든 엔티티 유형은 현실에서 발언할 수 있는 주체여야 하며, 추상적인 개념이어서는 안 됩니다.
5. 속성 이름으로 name, uuid, group_id 등의 예약어를 사용할 수 없으며, full_name, org_name 등으로 대체하십시오.
"""

        return message

    def _validate_and_process(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """결과 검증 및 후처리"""

        # 필수 필드 확인
        if "entity_types" not in result:
            result["entity_types"] = []
        if "edge_types" not in result:
            result["edge_types"] = []
        if "analysis_summary" not in result:
            result["analysis_summary"] = ""

        # 엔티티 유형 검증
        for entity in result["entity_types"]:
            if "attributes" not in entity:
                entity["attributes"] = []
            if "examples" not in entity:
                entity["examples"] = []
            # description이 100자를 초과하지 않도록 보장
            if len(entity.get("description", "")) > 100:
                entity["description"] = entity["description"][:97] + "..."

        # 관계 유형 검증
        for edge in result["edge_types"]:
            if "source_targets" not in edge:
                edge["source_targets"] = []
            if "attributes" not in edge:
                edge["attributes"] = []
            if len(edge.get("description", "")) > 100:
                edge["description"] = edge["description"][:97] + "..."

        # Zep API 제한: 최대 10개의 사용자 정의 엔티티 유형, 최대 10개의 사용자 정의 관계 유형
        MAX_ENTITY_TYPES = 10
        MAX_EDGE_TYPES = 10

        # 범용 유형 정의
        person_fallback = {
            "name": "Person",
            "description": "Any individual person not fitting other specific person types.",
            "attributes": [
                {
                    "name": "full_name",
                    "type": "text",
                    "description": "Full name of the person",
                },
                {"name": "role", "type": "text", "description": "Role or occupation"},
            ],
            "examples": ["ordinary citizen", "anonymous netizen"],
        }

        organization_fallback = {
            "name": "Organization",
            "description": "Any organization not fitting other specific organization types.",
            "attributes": [
                {
                    "name": "org_name",
                    "type": "text",
                    "description": "Name of the organization",
                },
                {
                    "name": "org_type",
                    "type": "text",
                    "description": "Type of organization",
                },
            ],
            "examples": ["small business", "community group"],
        }

        # 범용 유형 존재 여부 확인
        entity_names = {e["name"] for e in result["entity_types"]}
        has_person = "Person" in entity_names
        has_organization = "Organization" in entity_names

        # 추가가 필요한 범용 유형
        fallbacks_to_add = []
        if not has_person:
            fallbacks_to_add.append(person_fallback)
        if not has_organization:
            fallbacks_to_add.append(organization_fallback)

        if fallbacks_to_add:
            current_count = len(result["entity_types"])
            needed_slots = len(fallbacks_to_add)

            # 추가 시 10개를 초과하면 기존 유형 일부 제거
            if current_count + needed_slots > MAX_ENTITY_TYPES:
                # 제거할 개수 계산
                to_remove = current_count + needed_slots - MAX_ENTITY_TYPES
                # 끝부분부터 제거 (앞부분의 중요한 구체적 유형 보존)
                result["entity_types"] = result["entity_types"][:-to_remove]

            # 범용 유형 추가
            result["entity_types"].extend(fallbacks_to_add)

        # 최종적으로 제한을 초과하지 않도록 보장 (방어적 프로그래밍)
        if len(result["entity_types"]) > MAX_ENTITY_TYPES:
            result["entity_types"] = result["entity_types"][:MAX_ENTITY_TYPES]

        if len(result["edge_types"]) > MAX_EDGE_TYPES:
            result["edge_types"] = result["edge_types"][:MAX_EDGE_TYPES]

        return result

    def generate_python_code(self, ontology: Dict[str, Any]) -> str:
        """
        온톨로지 정의를 Python 코드로 변환 (ontology.py와 유사한 형식)

        Args:
            ontology: 온톨로지 정의

        Returns:
            Python 코드 문자열
        """
        code_lines = [
            '"""',
            "사용자 정의 엔티티 유형 정의",
            "MiroFish에 의해 자동 생성됨, 사회 여론 시뮬레이션용",
            '"""',
            "",
            "from pydantic import Field",
            "from zep_cloud.external_clients.ontology import EntityModel, EntityText, EdgeModel",
            "",
            "",
            "# ============== 엔티티 유형 정의 ==============",
            "",
        ]

        # 엔티티 유형 생성
        for entity in ontology.get("entity_types", []):
            name = entity["name"]
            desc = entity.get("description", f"A {name} entity.")

            code_lines.append(f"class {name}(EntityModel):")
            code_lines.append(f'    """{desc}"""')

            attrs = entity.get("attributes", [])
            if attrs:
                for attr in attrs:
                    attr_name = attr["name"]
                    attr_desc = attr.get("description", attr_name)
                    code_lines.append(f"    {attr_name}: EntityText = Field(")
                    code_lines.append(f'        description="{attr_desc}",')
                    code_lines.append(f"        default=None")
                    code_lines.append(f"    )")
            else:
                code_lines.append("    pass")

            code_lines.append("")
            code_lines.append("")

        code_lines.append("# ============== 관계 유형 정의 ==============")
        code_lines.append("")

        # 관계 유형 생성
        for edge in ontology.get("edge_types", []):
            name = edge["name"]
            # PascalCase 클래스명으로 변환
            class_name = "".join(word.capitalize() for word in name.split("_"))
            desc = edge.get("description", f"A {name} relationship.")

            code_lines.append(f"class {class_name}(EdgeModel):")
            code_lines.append(f'    """{desc}"""')

            attrs = edge.get("attributes", [])
            if attrs:
                for attr in attrs:
                    attr_name = attr["name"]
                    attr_desc = attr.get("description", attr_name)
                    code_lines.append(f"    {attr_name}: EntityText = Field(")
                    code_lines.append(f'        description="{attr_desc}",')
                    code_lines.append(f"        default=None")
                    code_lines.append(f"    )")
            else:
                code_lines.append("    pass")

            code_lines.append("")
            code_lines.append("")

        # 유형 딕셔너리 생성
        code_lines.append("# ============== 유형 설정 ==============")
        code_lines.append("")
        code_lines.append("ENTITY_TYPES = {")
        for entity in ontology.get("entity_types", []):
            name = entity["name"]
            code_lines.append(f'    "{name}": {name},')
        code_lines.append("}")
        code_lines.append("")
        code_lines.append("EDGE_TYPES = {")
        for edge in ontology.get("edge_types", []):
            name = edge["name"]
            class_name = "".join(word.capitalize() for word in name.split("_"))
            code_lines.append(f'    "{name}": {class_name},')
        code_lines.append("}")
        code_lines.append("")

        # 에지의 source_targets 매핑 생성
        code_lines.append("EDGE_SOURCE_TARGETS = {")
        for edge in ontology.get("edge_types", []):
            name = edge["name"]
            source_targets = edge.get("source_targets", [])
            if source_targets:
                st_list = ", ".join(
                    [
                        f'{{"source": "{st.get("source", "Entity")}", "target": "{st.get("target", "Entity")}"}}'
                        for st in source_targets
                    ]
                )
                code_lines.append(f'    "{name}": [{st_list}],')
        code_lines.append("}")

        return "\n".join(code_lines)
