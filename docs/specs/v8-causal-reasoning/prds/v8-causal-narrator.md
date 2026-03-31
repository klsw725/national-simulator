# PRD: 인과 내러티브 + LLM 하이브리드 추출

> Status: Draft
> Created: 2026-03-29
> Dependencies: v8-causal-reasoner (M1 완료 필수)
> 관련 스펙: V5-SPEC.md
> 버전: v8.3

---

## 1. 문제 정의

V8-2에서 DoWhy GCM 기반 인과 추론 엔진(개입/반사실/귀속)을 구축했지만, 두 가지 문제가 남아 있다:

1. **인과 DAG가 수동 구성에 의존**: 도메인 DAG는 엔지니어가 코드로 정의하고, 데이터 학습 DAG는 정형 데이터에서만 학습한다. OSINT 텍스트(뉴스, 정보 보고서)에 포함된 인과 관계를 자동으로 추출하지 못한다.

2. **인과 추론 결과가 사용자에게 전달되지 않음**: CausalReasoner가 수치(기여도 45%, 반사실 차이 -0.23)를 반환하지만, 이것이 브리핑 문서나 코파일럿 응답에서 분석관이 이해할 수 있는 내러티브로 변환되지 않는다.

### 현황

| 역량 | 현재 상태 | 필요 |
|------|----------|------|
| OSINT 텍스트 → 인과 관계 추출 | ❌ 없음 | LLM 하이브리드 추출 (가설 → 통계 검증) |
| 온톨로지 인과 엣지 | `RELATES_TO` (연관만) | `CAUSES`, `ENABLES`, `PREVENTS` 추가 |
| 브리핑 인과 설명 | LLM 서술적 내러티브 (근거 없음) | 인과 경로 + 추정치 기반 정량적 설명 |
| 코파일럿 인과 설명 | ❌ 없음 | DAG 경로 추적 + 추정치 기반 답변 |

### 제약 조건

- **LLM 인과추론 한계**: LLM 단독 인과 발견 F1=29%. 반드시 통계 검증과 결합
- **OpenAI-compatible API**: `response_format={"type": "json_object"}` 미지원 프로바이더 대비 폴백 필요
- **MiroFish 온톨로지**: 인과 엣지 타입 추가는 `ontology_generator.py`의 시스템 프롬프트 수정으로 가능 (MiroFish 코드 구조 변경 없음)

---

## 2. 솔루션 개요

**3계층 인과 내러티브 파이프라인: 추출 → 검증 → 내러티브.**

```
┌────────────────────────────────────────────────────────────────┐
│  Layer 1: Causal Extractor (LLM 하이브리드)                     │
│                                                                │
│  OSINT 텍스트 ──→ [LLM: 인과 엣지 후보 추출]                    │
│                         ↓                                      │
│                  [pgmpy: 통계 검증 (데이터 있을 때)]              │
│                         ↓                                      │
│                  검증된 인과 엣지 → DAG 업데이트                  │
└────────────────────────────┬───────────────────────────────────┘
                             ↓
┌────────────────────────────────────────────────────────────────┐
│  Layer 2: Ontology Extension                                   │
│                                                                │
│  온톨로지 생성 시스템 프롬프트에 인과 엣지 타입 추가              │
│  CAUSES, ENABLES, PREVENTS → Neo4j에 저장                      │
└────────────────────────────┬───────────────────────────────────┘
                             ↓
┌────────────────────────────────────────────────────────────────┐
│  Layer 3: Causal Narrator                                      │
│                                                                │
│  인과 DAG + DoWhy 추정치 ──→ [인과 경로 추출]                    │
│                                    ↓                           │
│                             [LLM: 경로 기반 내러티브 생성]       │
│                                    ↓                           │
│                        브리핑 + 코파일럿에 주입                  │
└────────────────────────────────────────────────────────────────┘
```

### 핵심 설계 결정

| 결정 | 선택 | 근거 |
|------|------|------|
| 인과 추출 패턴 | CauScientist 패턴 (LLM 가설 → 통계 검증) | F1 +53.8% (LLM 단독 대비). 하이브리드가 2026년 SOTA |
| LLM 출력 형식 | 구조화된 JSON (Pydantic 파싱) | 파싱 안정성. `response_format` 미지원 시 프롬프트 기반 폴백 |
| 검증 방식 | pgmpy 조건부 독립 검정 + BDeu | 데이터 있을 때만 검증. 없으면 LLM 추출 결과에 confidence="unverified" 표시 |
| 온톨로지 확장 | MiroFish `ontology_generator.py` 시스템 프롬프트 수정 | 코드 구조 변경 없이 인과 엣지 타입 추가 |
| 내러티브 생성 | DAG 경로 + 추정치를 LLM 프롬프트에 주입 | LLM이 자유 서술하는 것보다 인과 경로로 앵커링된 설명이 정확 |

---

## 3. 기술 상세

### 3.1 Causal Extractor

```python
# backend/app/services/causal_extractor.py

class CausalExtractor:
    """OSINT 텍스트에서 인과 관계를 추출하고 통계적으로 검증한다."""

    EXTRACTION_PROMPT = """\
주어진 텍스트에서 인과 관계를 추출하세요. 각 관계에 대해:
- cause: 원인 (변수 또는 이벤트)
- effect: 결과 (변수 또는 이벤트)
- relationship: "causes" | "enables" | "prevents"
- confidence: 0.0-1.0 (텍스트에서의 인과 근거 강도)
- evidence: 텍스트에서 인과 관계를 뒷받침하는 인용문

JSON 배열로 출력하세요. 상관 관계는 제외하고 인과 관계만 포함하세요.
"A와 B가 동시에 발생" → 상관 (제외)
"A로 인해 B가 발생" → 인과 (포함)
"A가 B를 가능하게 함" → enables (포함)
"A가 B를 억제함" → prevents (포함)
"""

    async def extract_from_text(
        self, text: str, existing_variables: list[str] | None = None,
    ) -> list[CausalEdge]:
        """LLM으로 텍스트에서 인과 엣지 후보를 추출한다."""
        # 1. 기존 변수 목록을 프롬프트에 포함 (변수명 정규화)
        # 2. LLM 호출 → JSON 파싱
        # 3. response_format 미지원 시 프롬프트 기반 JSON 추출 폴백
        # 4. CausalEdge 목록 반환 (provenance="llm_extracted")

    async def validate_with_data(
        self,
        candidates: list[CausalEdge],
        df: pd.DataFrame,
    ) -> list[CausalEdge]:
        """데이터 기반 통계 검증. 조건부 독립 검정으로 인과 방향 확인."""
        # 1. 각 후보 엣지에 대해:
        #    - pgmpy 조건부 독립 검정 (chi_square)
        #    - 독립이 기각되면 → 인과 관계 유지
        #    - 독립이 기각 안 되면 → 제거 또는 confidence 하향
        # 2. 검증된 엣지만 반환 (confidence 업데이트)

    async def extract_and_validate(
        self, text: str, df: pd.DataFrame | None = None,
    ) -> list[CausalEdge]:
        """추출 + 검증 통합 파이프라인."""
        # 1. extract_from_text()
        # 2. df가 있으면 validate_with_data()
        # 3. df가 없으면 confidence에 "unverified" 태그 추가
        # 4. 최종 엣지 목록 반환
```

### 3.2 온톨로지 인과 엣지 확장

MiroFish `ontology_generator.py`의 시스템 프롬프트에 인과 엣지 타입을 추가한다:

```python
# 현재 (연관 관계만):
# "Generate 6-10 edge types such as WORKS_FOR, SUPPORTS, OPPOSES..."

# 변경 후 (인과 관계 추가):
# "Generate 6-10 edge types. Include at minimum:
#  - CAUSES: A directly causes B (e.g., sanctions CAUSES economic_decline)
#  - ENABLES: A makes B possible (e.g., alliance ENABLES military_access)
#  - PREVENTS: A blocks or reduces B (e.g., diplomacy PREVENTS escalation)
#  Plus domain-specific types: SUPPORTS, OPPOSES, WORKS_FOR, etc."
```

DozerDB 클라이언트에 `causal_strength` 속성 지원을 추가한다:

```python
# dozerdb_client.py의 create_edge() 확장
# 기존 fact, fact_type 외에 optional causal_strength: float 추가
```

### 3.3 Causal Narrator

```python
# backend/app/services/causal_narrator.py

class CausalNarrator:
    """인과 DAG + 추정치를 분석관이 이해할 수 있는 내러티브로 변환한다."""

    NARRATIVE_PROMPT = """\
당신은 지정학 분석관입니다. 아래의 인과 분석 결과를 전문적인 브리핑 형식으로 설명하세요.

인과 경로:
{causal_paths}

각 경로의 인과 강도:
{attributions}

규칙:
- 인과 경로를 따라 "A → B → C" 형식으로 메커니즘을 설명하세요
- 각 단계의 기여도(%)를 포함하세요
- 신뢰구간을 괄호로 표시하세요
- "heuristic 추정치"임을 명시하세요
- 추측이 아닌 데이터 기반 결과만 서술하세요
"""

    async def generate_causal_narrative(
        self,
        dag: nx.DiGraph,
        target_variable: str,
        attribution: dict[str, float],
        context: str = "",
    ) -> str:
        """인과 DAG + 귀속 결과를 내러티브로 변환."""
        # 1. DAG에서 target의 ancestor → target 경로 추출
        # 2. 각 경로에 attribution 값 매핑
        # 3. 프롬프트에 주입 → LLM 내러티브 생성
        # 4. 내러티브 반환

    async def enrich_briefing(
        self,
        briefing_text: str,
        dag: nx.DiGraph,
        attributions: dict | None,
    ) -> str:
        """기존 브리핑 텍스트에 인과 분석 섹션을 추가."""
        # 1. attributions가 있으면 인과 내러티브 생성
        # 2. 브리핑 텍스트의 "지정학적 함의" 섹션 뒤에 "인과 분석" 섹션 추가
        # 3. 없으면 원본 텍스트 그대로 반환 (graceful degradation)
```

### 3.4 브리핑 생성기 통합

```python
# briefing_generator.py 확장

# 기존 프롬프트의 섹션 구조에 "인과 분석" 섹션 추가:
# ## 6. 인과 분석 (Causal Analysis)
# - 핵심 인과 경로 (DAG 경로 + 기여도)
# - 개입 시나리오 (do-calculus 결과 요약)
# - 반사실 평가 (핵심 반사실 1-2개)
# - 신뢰도 및 한계 (데이터 기반 추정임을 명시)

# generate_briefing() 수정:
# 1. CausalReasoner에서 인과 귀속 조회
# 2. CausalNarrator로 내러티브 생성
# 3. 브리핑 프롬프트에 인과 내러티브 주입
```

### 3.5 코파일럿 인과 설명 통합

```python
# copilot_context.py 확장

# 코파일럿의 컨텍스트 빌더에 인과 DAG 요약 추가:
# - 현재 시나리오의 인과 DAG 요약 (주요 경로 3-5개)
# - 최근 인과 쿼리 결과 (있으면)
# - 사용 가능한 인과 도구 설명

# 코파일럿이 "왜 X가 발생했는가?" 질문에:
# 1. DAG에서 X의 ancestor 경로 추출
# 2. CausalReasoner.attribute() 호출
# 3. CausalNarrator로 경로 기반 설명 생성
# 4. "경로 A→B→X (기여도 45%), 경로 C→X (기여도 30%)" 형식 답변
```

### 3.6 API 엔드포인트

```
POST /api/causal/extract
  Request:  { text: str, scenario_id?: str }
  Response: { edges: list[CausalEdge], verified: bool }
  동작: OSINT 텍스트에서 인과 관계 추출 + 데이터 검증 (데이터 있을 때)

GET  /api/causal/models/{model_id}/paths
  Query:    target: str, max_paths?: int (기본 5)
  Response: { paths: list[list[str]], attributions: dict }
  동작: 특정 변수까지의 인과 경로 + 기여도 조회

POST /api/causal/narrate
  Request:  { model_id: str, target_variable: str, context?: str }
  Response: { narrative: str, paths_used: int, confidence: str }
  동작: 인과 내러티브 생성
```

### 3.7 수정 대상 파일

```
# 신규
backend/app/services/causal_extractor.py             # LLM 하이브리드 인과 추출
backend/app/services/causal_narrator.py              # 인과 내러티브 생성

# 수정
backend/app/causal/models.py                         # 추출/내러티브 관련 모델 추가
backend/app/routers/causal.py                        # 추출/경로/내러티브 API 추가
backend/app/services/briefing_generator.py           # 인과 분석 섹션 추가
backend/app/services/copilot_context.py              # 인과 DAG 컨텍스트 + 설명 도구
external/mirofish-backend/app/services/ontology_generator.py  # 인과 엣지 타입 시스템 프롬프트
external/mirofish-backend/app/utils/dozerdb_client.py         # causal_strength 속성 (선택적)
```

---

## 4. 마일스톤

- [ ] **M1: LLM 인과 가설 추출기** — `CausalExtractor.extract_from_text()`: OSINT 텍스트 → 구조화된 인과 엣지 JSON. `response_format` 미지원 프로바이더 폴백.
  - 검증: 지정학 뉴스 텍스트 3개 입력 → 각각 3+ 인과 엣지 추출. JSON 파싱 성공

- [ ] **M2: 통계 검증 파이프라인** — `CausalExtractor.validate_with_data()`: pgmpy 조건부 독립 검정으로 LLM 추출 엣지 검증. `POST /api/causal/extract` 엔드포인트.
  - 검증: 30+ 관측치 + LLM 추출 엣지 → 검증 후 일부 엣지 confidence 변경 확인

- [ ] **M3: 온톨로지 인과 엣지 타입** — MiroFish 온톨로지 생성 프롬프트에 CAUSES/ENABLES/PREVENTS 추가. DozerDB에 인과 엣지 저장.
  - 검증: 시뮬레이션 실행 → 온톨로지에 CAUSES 타입 엣지 1+ 생성 확인

- [ ] **M4: 브리핑 + 코파일럿 인과 내러티브** — `CausalNarrator`: DAG 경로 + 추정치 → 내러티브. `briefing_generator.py`에 인과 분석 섹션 추가. 코파일럿에 인과 경로 기반 설명 통합.
  - 검증: 브리핑 문서에 "인과 분석" 섹션 포함. "경로 A→B→C (기여도 N%)" 형식. 코파일럿 "왜 긴장도가 높은가?" → 인과 경로 답변

---

## 5. 성공 기준

- OSINT 텍스트에서 인과 관계를 자동 추출하고 구조화된 JSON으로 반환한다
- 시뮬레이션 데이터가 있을 때 LLM 추출 엣지를 통계적으로 검증한다
- 온톨로지 생성 시 인과 엣지 타입(CAUSES, ENABLES, PREVENTS)이 포함된다
- 브리핑 문서에 인과 경로 기반 정량적 설명이 포함된다
- 코파일럿이 "왜" 질문에 인과 경로 + 기여도로 답한다
- 인과 데이터가 없어도 기존 기능이 정상 동작한다 (graceful degradation)

---

## 6. 위험 및 완화

| 위험 | 완화 |
|------|------|
| LLM이 허위 인과 관계 추출 (hallucination) | 통계 검증 필수. 미검증 엣지에 "unverified" 표시. 분석관 확인 UI |
| response_format 미지원 프로바이더에서 JSON 파싱 실패 | 프롬프트 기반 JSON 추출 폴백. 3회 재시도 |
| MiroFish 온톨로지 프롬프트 수정으로 기존 엣지 타입 품질 저하 | 인과 엣지를 "추가"로만 요청 (기존 타입 유지). 전후 비교 테스트 |
| 인과 내러티브가 과도하게 확정적으로 표현 | 프롬프트에 "heuristic 추정치" 명시 강제. 신뢰구간 필수 |
| 프로바이더별 LLM 품질 편차 | 추출 프롬프트를 모델 비특이적으로 설계. 최소 품질 임계치 미달 시 경고 |

---

## 진행 로그

| 날짜 | 상태 | 내용 |
|------|------|------|
| 2026-03-29 | Draft | V5 SPEC 기반 PRD 작성. LLM 하이브리드 인과 추출 (CauScientist 패턴) + 온톨로지 인과 엣지 + 브리핑/코파일럿 내러티브 통합 설계. |
