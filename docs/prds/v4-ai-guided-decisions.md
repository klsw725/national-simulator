# PRD: AI 가이드 결정 지점

> Status: Draft
> Created: 2026-03-21
> Dependencies: seed-generation, simulation-orchestration, v3-simulation-params
> 관련 스펙: `specs/V4-SPEC.md` PRD V4-1
> 버전: v4.0

---

## 1. 문제 정의

파이프라인의 모든 단계가 자동 실행되어 분석관이 핵심 결정에 개입할 수 없다. 시드는 단일 버전만 자동 생성되고, 시뮬레이션 파라미터는 분석관이 직접 설정해야 하며, AI가 상황에 맞는 권장 사항을 제시하지 않는다.

현재 상태:
- **SeedGenerator** — 1개 시드만 생성. 대안 없음. 분석관은 체크포인트 모드에서 텍스트를 수정할 수 있지만, 어떤 방향이 좋은지 AI가 제안하지 않음.
- **SimulationParams** — platform, hours, rounds 등을 분석관이 직접 설정. 지역/상황에 맞는 권장값 없음.
- **행위자 구성** — 온톨로지 생성 후 자동 결정. 분석관이 행위자를 추가/제거할 수 없음.

## 2. 솔루션 개요

파이프라인의 3개 핵심 결정 지점에서 AI가 선택지를 생성하고 분석관에게 제시한다.

**결정 지점 1: 시드 선택** — AI가 동일 OSINT 데이터에서 3-5개의 다른 관점(낙관/비관/중립/군사 중심/외교 중심)의 시드 초안을 생성. 분석관이 하나를 선택하거나 커스텀 수정.

**결정 지점 2: 행위자 구성** — 온톨로지 생성 후 AI가 행위자 목록과 역할/관계를 제안. 분석관이 행위자 추가/제거/역할 변경.

**결정 지점 3: 파라미터 권장** — AI가 지역, 관측된 군사 활동 수준, GDELT 긴장도에 따라 시뮬레이션 파라미터를 권장. 근거와 함께 제시.

## 3. 기술 상세

### 3.1 DecisionPoint 모델

```python
# backend/app/models/decision_point.py (신규)
class DecisionPointType(str, Enum):
    SEED_SELECTION = "seed_selection"
    ACTOR_CONFIGURATION = "actor_configuration"
    PARAMETER_RECOMMENDATION = "parameter_recommendation"

class DecisionOption(BaseModel):
    id: str
    label: str
    description: str
    confidence: float  # 0.0-1.0
    reasoning: str
    data: dict  # 옵션별 페이로드 (시드 텍스트, 행위자 목록, 파라미터 등)

class DecisionPoint(BaseModel):
    id: str
    scenario_id: str
    type: DecisionPointType
    options: list[DecisionOption]
    recommended: str  # 추천 옵션 ID
    allow_custom: bool = True
    status: str = "pending"  # pending | resolved
    selected_option_id: str | None = None
    custom_data: dict | None = None
    created_at: str
    resolved_at: str | None = None
```

### 3.2 AI 시드 옵션 생성기

SeedGenerator.generate()를 확장하여 다중 시드를 생성.

```python
async def generate_options(
    self, bbox, question, region_name, num_options=3, web_search_enabled=False
) -> list[dict]:
    """
    동일 OSINT 데이터에서 관점별 시드 초안 생성.
    관점: military_focus, diplomatic_focus, neutral, pessimistic, optimistic
    """
    # 1. OSINT 데이터 수집 (1회)
    # 2. LLM에 관점별 프롬프트로 num_options개 시드 병렬 생성
    # 3. 각 시드에 confidence + reasoning 첨부
```

### 3.3 AI 파라미터 권장 엔진

```python
class ParameterRecommender:
    async def recommend(
        self, region_name: str, tension_score: float,
        vessels_count: int, actors: list[str]
    ) -> DecisionOption:
        """
        관측 데이터 기반 시뮬레이션 파라미터 권장.
        - tension_score > 0.7 → hours=48, rounds=20
        - vessels_count > 10 → platform="twitter" (더 활발한 소셜 반응)
        - actors > 5 → geopolitics_enabled=True
        """
```

### 3.4 DecisionPoint API

```
POST /api/scenario/{id}/decision_points          → 결정 지점 생성 (파이프라인 자동)
GET  /api/scenario/{id}/decision_points           → 결정 지점 목록
GET  /api/scenario/{id}/decision_points/{dp_id}   → 결정 지점 상세
POST /api/scenario/{id}/decision_points/{dp_id}/resolve → 분석관 결정 제출
```

### 3.5 파이프라인 통합

```
기존: seed → ontology → graph → simulation → report
V4:   seed_options → [PAUSE: 분석관 선택] → ontology → [PAUSE: 행위자 확인]
      → graph → simulation → report
```

SimulationOrchestrator에 `interactive` 모드 추가. `interactive=true`이면 결정 지점에서 일시정지하고 분석관 응답을 기다린다.

### 3.6 프론트엔드 DecisionPointView

분석관에게 선택지를 카드 UI로 제시:
- 각 옵션: 제목 + 설명 + 신뢰도 바 + AI 추론 텍스트
- 추천 옵션 하이라이트
- "커스텀 입력" 옵션 (allow_custom=true)
- 선택 → POST resolve → 파이프라인 재개

### 3.7 수정 대상 파일

```
# 신규
backend/app/models/decision_point.py        # DecisionPoint, DecisionOption 모델
backend/app/services/parameter_recommender.py  # AI 파라미터 권장 엔진

# 수정
backend/app/database.py                     # decision_points 테이블
backend/app/services/seed_generator.py      # generate_options() 추가
backend/app/services/simulation_orchestrator.py  # interactive 모드 + 결정 지점 생성
backend/app/routers/simulation.py           # DecisionPoint API 엔드포인트
frontend/src/types/simulation.ts            # DecisionPoint 타입
frontend/src/components/simulation/DecisionPointView.tsx  # 신규: 선택지 UI
frontend/src/components/simulation/SimulationPanel.tsx    # 결정 지점 탭/뷰 통합
frontend/src/lib/gatewayApi.ts              # DecisionPoint API 호출
```

## 4. 마일스톤

- [x] **M1: DecisionPoint 모델 + API** — decision_points 테이블 생성. DecisionPoint/DecisionOption 모델 구현. CRUD API (생성, 조회, 결정 제출). 파이프라인에서 결정 지점 생성 시 상태를 "waiting_decision"으로 설정.
  - 검증: POST /decision_points 생성 → GET 조회 → POST resolve → 상태 변경

- [x] **M2: AI 시드 옵션 생성기** — SeedGenerator.generate_options() 구현. 동일 OSINT 데이터에서 관점별 프롬프트로 3개 시드 병렬 생성. 각 시드에 confidence + reasoning 첨부. DecisionPoint 타입 seed_selection으로 저장.
  - 검증: 시드 생성 시 3개 옵션이 생성되어 decision_points에 저장

- [x] **M3: AI 파라미터 권장 엔진** — ParameterRecommender 구현. 지역/긴장도/행위자 수 기반 파라미터 권장. DecisionPoint 타입 parameter_recommendation으로 저장. 근거 텍스트 생성.
  - 검증: 시나리오 생성 시 AI가 파라미터 권장값 + 근거 제시

- [x] **M4: 프론트엔드 DecisionPointView** — 선택지 카드 UI (제목, 설명, 신뢰도 바, AI 추론). 추천 옵션 하이라이트. 커스텀 입력 지원. 선택 → resolve API 호출 → 파이프라인 재개.
  - 검증: 시드 선택 결정 지점에서 3개 옵션 카드 표시 → 선택 → 파이프라인 진행

- [x] **M5: SimulationOrchestrator interactive 모드 통합** — interactive=true일 때 시드 생성 후 일시정지. 분석관 결정 후 재개. 파라미터 권장 표시. 기존 auto 모드 유지.
  - 검증: interactive 모드로 시나리오 실행 → 시드 선택 지점에서 일시정지 → 선택 후 진행

## 5. 성공 기준

- AI가 시드 생성 시 3-5개 관점별 옵션을 제시한다
- 분석관이 옵션을 선택하거나 커스텀 수정할 수 있다
- AI가 시뮬레이션 파라미터를 상황에 맞게 권장하고 근거를 제시한다
- 기존 auto 모드가 변경 없이 동작한다 (하위 호환)

## 6. 위험 및 완화

| 위험 | 완화 |
|------|------|
| 3-5개 시드 병렬 생성으로 LLM 비용 3-5배 | 기본 3개, 최대 5개 제한. 캐싱 |
| 분석관이 결정 지점에서 장시간 미응답 | 타임아웃 설정 (기본 30분). auto 모드 폴백 옵션 |
| AI 권장이 부정확 | confidence 점수 표시. 분석관이 항상 override 가능 |

## 7. 참고

### 관련 PRD
- **seed-generation** — 현재 SeedGenerator 구현
- **v3-simulation-params** — SimulationParams (V4에서 AI 권장 대상)
- **v3-intelligent-seed** — ER + PostGIS 컨텍스트 (시드 옵션에도 반영)
- **v4-interactive-simulation (V4-2)** — 시뮬레이션 중 결정 지점 (후속)

## 진행 로그

| 날짜 | 상태 | 내용 |
|------|------|------|
| 2026-03-21 | Draft | V4-1 AI 가이드 결정 지점 PRD 초안 작성 |
| 2026-03-21 | M1 Complete | DecisionPoint 모델 + decision_points 테이블 + CRUD API 4개 + 프론트엔드 타입/API 클라이언트 구현 |
| 2026-03-21 | M2 Complete | SeedGenerator.generate_options() — 3개 관점별(군사/외교/균형) 시드 병렬 생성 + OSINT 기반 confidence + DecisionPoint 자동 저장 |
| 2026-03-21 | M3 Complete | param_recommender.recommend_params() — quick/standard/deep 3개 파라미터 옵션 + OSINT 메타데이터 기반 자동 추천 |
| 2026-03-21 | M4 Complete | DecisionPointView 컴포넌트 — 옵션 카드 UI + confidence 바 + AI 추천 배지 + 커스텀 입력 + SimulationPanel 통합 |
| 2026-03-21 | M5 Complete | mode=interactive 파이프라인 — 백그라운드 옵션 생성 → checkpoint:decision 일시정지 → 분석관 선택 → 시드/파라미터 적용 → 파이프라인 재개 |
