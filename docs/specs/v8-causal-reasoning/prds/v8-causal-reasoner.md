# PRD: 인과 추론 엔진

> Status: Draft
> Created: 2026-03-29
> Dependencies: v8-causal-dag (M1, M2 완료 필수)
> 관련 스펙: V5-SPEC.md
> 버전: v8.2

---

## 1. 문제 정의

V8-1에서 인과 DAG와 시뮬레이션 로그 수집 파이프라인을 구축했지만, DAG 위에서 실제 인과 추론을 수행하는 엔진이 없다.

분석관이 던지는 핵심 질문 3가지에 답할 수 없다:

1. **개입**: "do(제재=강화)하면 분쟁 확률이 얼마나 오르는가?" → 현재 답 불가
2. **반사실**: "제재를 하지 않았다면 분쟁이 일어났을까?" → 현재 What-If는 전체 재실행뿐
3. **귀속**: "긴장도 0.8 중 군사훈련이 몇 %, 제재가 몇 %를 설명하는가?" → 현재 답 불가

### 현황

| 역량 | 현재 상태 | 필요 |
|------|----------|------|
| 개입 쿼리 (do-calculus) | ❌ 없음 | DoWhy GCM `interventional_samples()` |
| 반사실 쿼리 | What-If 전체 재실행 (비용 높음, 인과 아님) | DoWhy GCM `counterfactual_samples()` |
| 인과 귀속 | ❌ 없음 | DoWhy GCM 기반 Shapley 인과 귀속 |
| 이질적 효과 | ❌ 없음 | EconML CATE (강대국 vs 소국 효과 차이) |
| What-If 인과 분석 | 키워드 긴장도 비교만 | 인과 귀속 추가 |
| 코파일럿 인과 쿼리 | ❌ 없음 | 자연어 → 개입/반사실 쿼리 변환 |

### 제약 조건

- **OpenAI-compatible API**: structured output 지원 여부가 프로바이더마다 다름. JSON 파싱 폴백 필요
- **DoWhy GCM 적합 시간**: SCM fit은 데이터 크기에 따라 1~10초. 실시간 API에서는 사전 적합 + 캐싱 필요
- **최소 데이터량**: GCM 적합에 최소 30+ 관측치. 도메인 DAG만으로도 개입 쿼리는 가능 (규칙 기반 시뮬레이션)

---

## 2. 솔루션 개요

**DoWhy GCM 기반 3가지 인과 쿼리 엔진 + What-If 인과 귀속 + 코파일럿 통합.**

```
                    인과 DAG (V8-1)
                         │
                         ▼
              ┌─────────────────────┐
              │   CausalReasoner    │
              │   (DoWhy GCM)       │
              │                     │
              │  fit(dag, df) ──────│──→ 사전 적합된 SCM (캐싱)
              │                     │
              │  intervene(var, v) ─│──→ "do(X=v)하면 Y 분포는?"
              │  counterfact(obs) ──│──→ "X가 달랐다면 Y는?"
              │  attribute(target) ─│──→ "Y의 원인별 기여도는?"
              └──────────┬──────────┘
                         │
            ┌────────────┼────────────┐
            ↓            ↓            ↓
     What-If 귀속   코파일럿 쿼리   API 엔드포인트
     (WhatIfEngine  (CopilotContext  (POST /api/causal/*)
      확장)          확장)
```

### 핵심 설계 결정

| 결정 | 선택 | 근거 |
|------|------|------|
| 인과 추론 프레임워크 | DoWhy GCM (v0.14) | 개입+반사실+귀속 모두 지원하는 유일한 Python 라이브러리. PyWhy 생태계 (MS 후원) |
| SCM 적합 전략 | `gcm.auto.assign_causal_mechanisms` | 자동으로 선형/비선형 모형 선택. 도메인 전문가 개입 최소화 |
| 캐싱 | 시나리오별 적합 SCM pickle 저장 | API 응답 시간 1초 미만 유지. 새 데이터 추가 시 재적합 |
| 인과 귀속 | DoWhy `attribute_anomalies` 또는 Shapley 기반 | 각 원인 변수의 결과 기여도를 정량화 |
| 이질적 효과 (CATE) | EconML `CausalForestDML` | 행위자 유형별 효과 차이 추정. V8-2에서는 API만 준비, 본격 활용은 V8-3 |
| 코파일럿 통합 | 자연어 → 구조화된 쿼리 변환 (LLM) | "제재를 강화하면?"→ `intervene(sanctions_intensity, 0.9)` |

---

## 3. 기술 상세

### 3.1 CausalReasoner 서비스

```python
# backend/app/services/causal_reasoner.py

class CausalReasoner:
    """DoWhy GCM 기반 인과 추론 엔진."""

    def __init__(self):
        self._fitted_models: dict[str, gcm.InvertibleStructuralCausalModel] = {}

    async def fit(
        self, model_id: str, dag: nx.DiGraph, df: pd.DataFrame
    ) -> dict:
        """SCM을 시뮬레이션 로그에 적합한다."""
        # 1. dag에서 InvertibleStructuralCausalModel 생성
        # 2. gcm.auto.assign_causal_mechanisms(scm, df) — 자동 모형 선택
        # 3. gcm.fit(scm, df)
        # 4. self._fitted_models[model_id] = scm
        # 5. 적합 메타데이터 반환 (변수 수, 관측치 수, 모형 타입)

    async def intervene(
        self,
        model_id: str,
        interventions: dict[str, float],
        target_variables: list[str] | None = None,
        num_samples: int = 500,
    ) -> dict:
        """개입 쿼리: do(X=v)하면 Y의 분포는?"""
        # 1. 적합된 SCM 조회
        # 2. interventions = {var: lambda _: value for var, value in ...}
        # 3. samples = gcm.interventional_samples(scm, interventions, num_samples)
        # 4. target_variables에 대한 통계 요약 (mean, std, CI) 반환

    async def counterfactual(
        self,
        model_id: str,
        observed_data: dict[str, float],
        interventions: dict[str, float],
    ) -> dict:
        """반사실 쿼리: 관측된 상황에서 X가 달랐다면 Y는?"""
        # 1. 적합된 SCM 조회
        # 2. observed_df = pd.DataFrame([observed_data])
        # 3. interventions = {var: lambda _: value for var, value in ...}
        # 4. cf = gcm.counterfactual_samples(scm, interventions, observed_df)
        # 5. 원본 vs 반사실 비교 반환

    async def attribute(
        self,
        model_id: str,
        target_variable: str,
        observed_data: dict[str, float] | None = None,
    ) -> dict:
        """인과 귀속: target_variable의 값에 각 원인이 기여한 정도."""
        # 1. 적합된 SCM 조회
        # 2. DAG에서 target의 ancestor 노드 추출
        # 3. 각 ancestor에 대해 개입 효과 추정 (Shapley 기반)
        # 4. {원인 변수: 기여도(%)} 반환
```

### 3.2 Pydantic 모델 (추가)

```python
class InterventionRequest(BaseModel):
    model_id: str
    interventions: dict[str, float]        # {변수명: 개입값}
    target_variables: list[str] | None = None  # None이면 전체
    num_samples: int = 500

class InterventionResult(BaseModel):
    interventions: dict[str, float]
    targets: dict[str, dict]               # {변수: {mean, std, ci_lower, ci_upper}}
    num_samples: int

class CounterfactualRequest(BaseModel):
    model_id: str
    observed: dict[str, float]             # 실제 관측값
    interventions: dict[str, float]        # 반사실 개입

class CounterfactualResult(BaseModel):
    observed: dict[str, float]
    counterfactual: dict[str, float]       # 반사실 세계의 추정값
    differences: dict[str, float]          # 차이 (반사실 - 관측)

class AttributionResult(BaseModel):
    target_variable: str
    target_value: float | None
    attributions: dict[str, float]         # {원인: 기여도 %}
    total_explained: float                 # 설명된 비율
```

### 3.3 API 엔드포인트

```
POST /api/causal/fit
  Request:  { model_id: str, scenario_id?: str }
  Response: { model_id: str, variables: int, observations: int, status: "fitted" }
  동작: DAG + 시뮬레이션 로그로 SCM 적합. 데이터 부족 시 도메인 DAG만으로 적합

POST /api/causal/intervene
  Request:  InterventionRequest
  Response: InterventionResult
  동작: do(X=v) 개입 쿼리 실행. SCM 미적합 시 자동 적합 시도

POST /api/causal/counterfactual
  Request:  CounterfactualRequest
  Response: CounterfactualResult
  동작: 반사실 쿼리 실행

POST /api/causal/attribute
  Request:  { model_id: str, target_variable: str, observed?: dict }
  Response: AttributionResult
  동작: 인과 귀속 계산
```

### 3.4 What-If 인과 귀속 통합

```python
# whatif_engine.py의 compare() 확장

class WhatIfComparison(BaseModel):
    # ... 기존 필드 유지
    tension_advantage: float
    tension_curves: dict
    step_variance: dict
    slope_variance: dict
    actor_diff: dict
    action_count_delta: int
    geopolitics_delta: int
    # 신규: 인과 귀속
    causal_attribution: dict | None = None
    # {
    #   "tension_advantage_explained": {
    #     "military_movement": 0.45,   # 45% 기여
    #     "sanction_impose": 0.30,     # 30% 기여
    #     "diplomatic_statement": 0.15, # 15% 기여
    #     "unexplained": 0.10          # 미설명 10%
    #   },
    #   "confidence": "medium",
    #   "data_points": 150,
    #   "method": "shapley_attribution"
    # }
```

`compare()` 메서드 수정:
1. 기존 MAXS 메트릭 계산 (변경 없음)
2. `CausalReasoner`가 적합된 상태이면:
   - 원본 결과의 라운드별 상태 변수 추출
   - 분기 결과의 라운드별 상태 변수 추출
   - 차이를 발생시킨 원인 변수별 귀속도 계산
   - `causal_attribution` 필드에 추가
3. 적합 안 됐으면 `causal_attribution = None` (graceful degradation)

### 3.5 코파일럿 인과 쿼리 통합

```python
# copilot_context.py 확장

# 코파일럿 도구 추가
CAUSAL_TOOLS = [
    {
        "name": "causal_intervene",
        "description": "인과 개입 쿼리. '제재를 강화하면 분쟁이?' 같은 질문에 답합니다.",
        "parameters": {
            "variable": "개입할 변수명",
            "value": "설정할 값 (0.0-1.0)",
            "target": "관찰할 결과 변수명",
        },
    },
    {
        "name": "causal_counterfactual",
        "description": "반사실 쿼리. '제재가 없었다면?' 같은 질문에 답합니다.",
        "parameters": {
            "observed": "현재 관측 상태",
            "change_variable": "변경할 변수",
            "change_value": "반사실 값",
        },
    },
    {
        "name": "causal_explain",
        "description": "인과 귀속. '왜 긴장도가 높은가?' 같은 질문에 답합니다.",
        "parameters": {
            "target_variable": "설명할 변수명",
        },
    },
]
```

코파일럿은 자연어 질문을 받으면 LLM이 적절한 도구를 선택하고 파라미터를 추출하여 `CausalReasoner`를 호출한다.

### 3.6 수정 대상 파일

```
# 신규
backend/app/services/causal_reasoner.py              # DoWhy GCM 인과 추론 엔진

# 수정
backend/app/causal/models.py                         # 추론 관련 Pydantic 모델 추가
backend/app/routers/causal.py                        # 추론 API 엔드포인트 추가
backend/app/models/interactive.py                    # WhatIfComparison에 causal_attribution 추가
backend/app/services/whatif_engine.py                # compare()에 인과 귀속 로직 추가
backend/app/services/copilot_context.py              # 인과 도구 추가
```

---

## 4. 마일스톤

- [ ] **M1: DoWhy GCM SCM 적합 + 개입 쿼리** — `CausalReasoner.fit()`: DAG + DataFrame → SCM 적합. `CausalReasoner.intervene()`: do(X=v) 쿼리. `POST /api/causal/fit`, `POST /api/causal/intervene` 엔드포인트.
  - 검증: 도메인 DAG + 30+ 관측치로 적합 → `intervene(threat_perception, 0.9)` → `conflict_outcome` 평균 상승 확인

- [ ] **M2: 반사실 쿼리 + API** — `CausalReasoner.counterfactual()`: 관측값 기준 "X가 달랐다면" 쿼리. `POST /api/causal/counterfactual` 엔드포인트.
  - 검증: 실제 시뮬레이션 라운드 관측값으로 `counterfactual(sanctions=0)` → `conflict_outcome` 감소 확인

- [ ] **M3: What-If 인과 귀속** — `CausalReasoner.attribute()`: 원인별 기여도 계산. `WhatIfComparison.causal_attribution` 필드 추가. `whatif_engine.compare()` 확장.
  - 검증: What-If 분기 비교 시 `causal_attribution`에 원인별 기여도(%) 표시. 합계 ≈ 100%

- [ ] **M4: 코파일럿 인과 쿼리 통합** — 코파일럿 도구에 `causal_intervene`, `causal_counterfactual`, `causal_explain` 추가. 자연어 → 인과 쿼리 변환.
  - 검증: "제재를 강화하면 분쟁이 어떻게 되나?" → 코파일럿이 `intervene` 도구 호출 → 정량적 답변

---

## 5. 성공 기준

- 개입 쿼리로 "do(X=v)하면 Y 평균이 Z (95% CI: [a, b])"라는 정량적 답변을 제공한다
- 반사실 쿼리로 "X가 달랐다면 Y는 Z → W로 변했을 것"이라는 답변을 제공한다
- What-If 비교에서 tension_advantage의 인과 귀속이 원인별 기여도(%)로 표시된다
- 코파일럿에서 자연어 인과 질문에 정량적으로 답한다
- SCM 미적합 상태에서도 graceful degradation (causal_attribution = null)

---

## 6. 위험 및 완화

| 위험 | 완화 |
|------|------|
| DoWhy GCM 적합 시 데이터 부족으로 불안정한 추정 | 최소 관측치 가드레일 (30+). 신뢰구간 필수 표시. 데이터 부족 시 경고 메시지 |
| SCM 적합 시간이 실시간 API에 부적합 | 사전 적합 + pickle 캐싱. 추론만 실시간 (< 1초) |
| 인과 귀속의 Shapley 계산 비용 (변수 수 증가 시 지수적) | 최대 변수 수 15개 제한. ancestor 노드만 대상 |
| 코파일럿이 부적절한 인과 쿼리를 생성 | 도구 파라미터에 유효 변수 목록 제공. 잘못된 변수명 → 422 반환 |
| 비전문가 분석관이 인과 결과를 오해석 | 결과에 해석 가이드 포함. "이 추정은 N개 시뮬레이션 데이터 기반" 명시 |

---

## 진행 로그

| 날짜 | 상태 | 내용 |
|------|------|------|
| 2026-03-29 | Draft | V5 SPEC 기반 PRD 작성. DoWhy GCM 기반 인과 추론 엔진 설계. 개입/반사실/귀속 3가지 쿼리 타입. What-If + 코파일럿 통합 설계. |
