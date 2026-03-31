# PRD: 인과 DAG 기반 구축

> Status: Draft
> Created: 2026-03-29
> Dependencies: 없음 (V5 기반 PRD)
> 관련 스펙: V5-SPEC.md
> 버전: v8.1

---

## 1. 문제 정의

지정학 엔진의 `PROPAGATION_RULES`와 `CASCADE_RULES`는 인과 관계를 암묵적으로 인코딩하고 있다. `military_movement → threat_perception +0.15`는 사실상 "군사 이동이 위협 인식을 높인다"라는 인과 주장이지만, 이것이 공식 인과 그래프로 표현되지 않아 do-calculus, 반사실 추론, 인과 귀속이 불가능하다.

또한 시뮬레이션 로그(에이전트 액션, 지정학 이벤트, 행위자 상태 변화)가 인과 분석용 정형 데이터로 수집되지 않아, 데이터 기반 인과 구조 학습도 불가능하다.

### 현황

| 역량 | 현재 상태 | 필요 |
|------|----------|------|
| 인과 규칙 표현 | `PROPAGATION_RULES` dict (Python) | NetworkX DiGraph (공식 DAG) |
| 캐스케이드 체인 표현 | `CASCADE_RULES` dict (조건부 트리거) | DAG 내 조건부 인과 엣지 |
| 시뮬레이션 로그 수집 | JSON 텍스트로 `simulation_results.results`에 저장 | 라운드별 상태 변수 DataFrame |
| 데이터 기반 구조 학습 | ❌ 없음 | pgmpy PC/HillClimb + 부트스트랩 |
| DAG 저장 | ❌ 없음 | PostgreSQL (메타데이터) + Neo4j (그래프 구조) |
| DAG 시각화 | ❌ 없음 | API로 노드/엣지 반환 → 프론트엔드 D3.js |

### 제약 조건

- **DAG 순환 금지**: 지정학 피드백 루프(`conflict → sanctions → conflict`)는 시간 언롤링으로 표현 (`conflict_t0 → sanctions_t1 → conflict_t2`)
- **최소 데이터량**: pgmpy 구조 학습에 100+ 시뮬레이션 런 필요. 축적 전까지 도메인 DAG만 사용
- **MiroFish 무수정**: 로그 수집은 Gateway 레이어에서 MiroFish 결과를 파싱. MiroFish 소스 변경 없음

---

## 2. 솔루션 개요

**2단계 DAG 구축**: 도메인 지식 DAG (즉시) + 데이터 학습 DAG (축적 후).

```
Phase 1: 도메인 지식 DAG (규칙 기반, 즉시 사용 가능)

  PROPAGATION_RULES ──→ ┌─────────────────────────────────────┐
  CASCADE_RULES ────────→│  도메인 DAG (NetworkX DiGraph)       │
  DECISION_RULES ───────→│                                     │
                         │  노드: 상태 변수 + 이벤트 타입       │
                         │  엣지: 인과 관계 (방향 + 강도)       │
                         └──────────────┬──────────────────────┘
                                        ↓
                                   DAG 저장소 (DB)

Phase 2: 데이터 학습 DAG (시뮬레이션 로그 축적 후)

  시뮬레이션 로그 ──→ ┌──────────────────────────────────────┐
  (DataFrame)        │  pgmpy HillClimb + BDeu               │
                     │  + 부트스트랩 50회 → 70%+ 안정 엣지    │
                     └──────────────┬───────────────────────┘
                                    ↓
                            학습된 DAG 후보
                                    ↓
                     도메인 DAG와 비교/병합 → 최종 DAG
```

### 핵심 설계 결정

| 결정 | 선택 | 근거 |
|------|------|------|
| DAG 표현 | NetworkX DiGraph | DoWhy GCM의 입력 포맷. 표준 그래프 라이브러리 |
| 도메인 DAG 소스 | 기존 PROPAGATION_RULES/CASCADE_RULES | 이미 검증된 규칙. 신규 가정 최소화 |
| 구조 학습 | pgmpy HillClimb + BDeu | Score-based 방법이 constraint-based(PC)보다 소규모 데이터에 안정적 |
| 부트스트랩 임계치 | 70% (50회 리샘플링) | CauScientist/causalif 논문 권장값 |
| 저장소 | PostgreSQL (메타데이터) + JSON (DAG 직렬화) | Neo4j 인과 엣지는 V8-3에서 확장. 이 단계는 분석용 DAG만 |
| 시계열 처리 | 시간 언롤링 (`var_t0`, `var_t1`, ...) | DoWhy GCM의 시계열 제한 회피. 라운드 단위 이산 시간 |

---

## 3. 기술 상세

### 3.1 DB 스키마

```sql
-- 인과 모형 메타데이터
CREATE TABLE IF NOT EXISTS causal_models (
    id TEXT PRIMARY KEY,
    scenario_id TEXT REFERENCES scenarios(id),
    model_type TEXT NOT NULL,              -- 'domain' | 'learned' | 'merged'
    dag_json TEXT NOT NULL,                -- NetworkX node_link_data JSON
    variables TEXT NOT NULL,               -- JSON: 변수 목록 + 설명
    fit_metadata TEXT,                     -- JSON: 적합 통계 (샘플 수, BDeu 점수 등)
    status TEXT DEFAULT 'active',          -- 'active' | 'superseded'
    created_at TEXT NOT NULL,
    updated_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_causal_models_scenario ON causal_models(scenario_id);
CREATE INDEX IF NOT EXISTS idx_causal_models_type ON causal_models(model_type);

-- 시뮬레이션 로그 수집 (라운드별 상태 스냅샷)
CREATE TABLE IF NOT EXISTS causal_observations (
    id SERIAL PRIMARY KEY,
    scenario_id TEXT NOT NULL REFERENCES scenarios(id),
    result_id TEXT NOT NULL,
    round_num INTEGER NOT NULL,
    variables JSONB NOT NULL,              -- {threat_perception: 0.6, resource_level: 0.4, ...}
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_causal_obs_scenario ON causal_observations(scenario_id);
CREATE INDEX IF NOT EXISTS idx_causal_obs_result ON causal_observations(result_id);
```

### 3.2 Pydantic 모델

```python
class CausalVariable(BaseModel):
    name: str                              # "threat_perception"
    description: str                       # "위협 인식 수준 [0.0-1.0]"
    var_type: str = "continuous"            # "continuous" | "discrete" | "binary"
    domain: tuple[float, float] | None = None  # (0.0, 1.0)

class CausalEdge(BaseModel):
    source: str                            # 원인 변수
    target: str                            # 결과 변수
    edge_type: str = "causes"              # "causes" | "enables" | "prevents"
    strength: float | None = None          # 인과 강도 (도메인 DAG: 규칙값, 학습: 추정값)
    confidence: float | None = None        # 부트스트랩 안정성 (학습 DAG만)
    provenance: str = "domain"             # "domain" | "learned" | "llm_extracted"

class CausalDAG(BaseModel):
    id: str
    scenario_id: str | None
    model_type: str                        # "domain" | "learned" | "merged"
    variables: list[CausalVariable]
    edges: list[CausalEdge]
    fit_metadata: dict | None = None
    created_at: str

class CausalObservation(BaseModel):
    scenario_id: str
    result_id: str
    round_num: int
    variables: dict[str, float]            # {변수명: 값}
```

### 3.3 도메인 DAG 생성기

```python
# backend/app/causal/domain_dag.py

def build_domain_dag() -> nx.DiGraph:
    """지정학 엔진의 PROPAGATION_RULES/CASCADE_RULES를 공식 DAG로 변환."""
    G = nx.DiGraph()

    # 상태 변수 노드
    state_vars = [
        "threat_perception", "domestic_pressure",
        "resource_level", "international_support",
    ]
    for var in state_vars:
        G.add_node(var, node_type="state_variable")

    # 이벤트 타입 노드
    event_types = [
        "military_movement", "military_exercise", "sanction_impose",
        "trade_restriction", "diplomatic_statement", "treaty_sign",
        "official_response", "alliance_support",
    ]
    for evt in event_types:
        G.add_node(evt, node_type="event_type")

    # 결과 노드
    G.add_node("escalation_decision", node_type="decision")
    G.add_node("conflict_outcome", node_type="outcome")

    # PROPAGATION_RULES → 인과 엣지 (이벤트 → 상태 변화)
    # 실제 강도값은 events.py의 PROPAGATION_RULES에서 추출
    propagation_edges = [
        ("military_movement", "threat_perception", 0.15),
        ("military_movement", "domestic_pressure", 0.05),
        ("military_exercise", "threat_perception", 0.08),
        ("sanction_impose", "resource_level", -0.20),
        ("sanction_impose", "domestic_pressure", 0.15),
        ("trade_restriction", "resource_level", -0.10),
        ("diplomatic_statement", "domestic_pressure", -0.05),
        ("diplomatic_statement", "international_support", 0.10),
        ("treaty_sign", "international_support", 0.15),
        ("treaty_sign", "threat_perception", -0.10),
        ("official_response", "domestic_pressure", -0.03),
        ("alliance_support", "international_support", 0.08),
    ]
    for src, tgt, strength in propagation_edges:
        G.add_edge(src, tgt, strength=strength, edge_type="causes", provenance="domain")

    # DECISION_RULES → 인과 엣지 (상태 → 결정)
    decision_edges = [
        ("threat_perception", "escalation_decision", 0.6),
        ("resource_level", "escalation_decision", 0.3),
        ("domestic_pressure", "escalation_decision", 0.4),
        ("international_support", "escalation_decision", 0.2),
    ]
    for src, tgt, strength in decision_edges:
        G.add_edge(src, tgt, strength=strength, edge_type="causes", provenance="domain")

    # 결정 → 결과
    G.add_edge("escalation_decision", "conflict_outcome",
               strength=0.7, edge_type="causes", provenance="domain")

    assert nx.is_directed_acyclic_graph(G), "도메인 DAG에 순환이 존재합니다"
    return G
```

### 3.4 시뮬레이션 로그 수집기

```python
# backend/app/services/causal_log_collector.py

class CausalLogCollector:
    """시뮬레이션 결과에서 인과 분석용 라운드별 상태 변수를 추출한다."""

    async def collect_from_result(
        self, scenario_id: str, result_id: str
    ) -> list[CausalObservation]:
        """시뮬레이션 결과 + 지정학 이벤트에서 라운드별 상태 스냅샷을 생성."""
        # 1. simulation_results에서 actions 파싱
        # 2. geopolitics_events에서 라운드별 이벤트 조회
        # 3. 라운드별 상태 변수 계산:
        #    - tension_ratio: 긴장 키워드 액션 비율
        #    - action_diversity: 고유 액션 타입 수
        #    - actor_activity: 활성 행위자 수
        #    - geo_event_count: 지정학 이벤트 수
        #    - escalation_level: 군사/제재 이벤트 비율
        # 4. causal_observations 테이블에 INSERT
        # 5. CausalObservation 목록 반환

    async def build_dataframe(
        self, scenario_id: str, min_results: int = 5
    ) -> pd.DataFrame | None:
        """수집된 관측치를 인과 분석용 DataFrame으로 변환."""
        # 1. causal_observations에서 scenario_id로 조회
        # 2. min_results 미만이면 None 반환 (데이터 부족 가드레일)
        # 3. 시간 언롤링: round_num → 별도 행 (패널 데이터 구조)
        # 4. pd.DataFrame 반환
```

### 3.5 구조 학습 서비스

```python
# backend/app/causal/structure_learner.py

class CausalStructureLearner:
    """시뮬레이션 로그에서 인과 구조를 학습한다."""

    def learn_structure(
        self,
        df: pd.DataFrame,
        n_bootstrap: int = 50,
        stability_threshold: float = 0.7,
    ) -> nx.DiGraph:
        """HillClimb + BDeu + 부트스트랩 안정성 검증."""
        # 1. 연속 변수 이산화 (KBinsDiscretizer)
        # 2. 부트스트랩 루프:
        #    for _ in range(n_bootstrap):
        #        sample = df.sample(n=len(df), replace=True)
        #        hc = HillClimbSearch(sample)
        #        model = hc.estimate(scoring_method=BDeuScore(sample))
        #        edge_counts[edge] += 1
        # 3. stability_threshold 이상 엣지만 유지
        # 4. nx.DiGraph 반환 (DAG 검증 포함)

    def compare_with_domain(
        self,
        learned_dag: nx.DiGraph,
        domain_dag: nx.DiGraph,
    ) -> dict:
        """학습 DAG vs 도메인 DAG 비교."""
        # 반환:
        # - confirmed: 양쪽 모두 존재하는 엣지 (도메인 지식 확인)
        # - discovered: 학습에서만 발견된 엣지 (새로운 인과 관계 후보)
        # - missing: 도메인에만 존재하는 엣지 (데이터 부족 또는 규칙 오류)
        # - reversed: 방향이 반대인 엣지 (인과 방향 재검토 필요)

    def merge_dags(
        self,
        domain_dag: nx.DiGraph,
        learned_dag: nx.DiGraph,
        domain_priority: bool = True,
    ) -> nx.DiGraph:
        """도메인 DAG + 학습 DAG 병합. 충돌 시 domain_priority에 따라 결정."""
```

### 3.6 API 엔드포인트

```
GET  /api/causal/domain_dag
  Response: CausalDAG
  동작: 도메인 지식 DAG 반환 (항상 사용 가능)

POST /api/causal/learn
  Request:  { scenario_id: str, n_bootstrap?: int, stability_threshold?: float }
  Response: CausalDAG (model_type="learned") + 도메인 DAG 비교 결과
  동작: 시뮬레이션 로그에서 구조 학습 실행. 최소 데이터량 미충족 시 422 반환

GET  /api/causal/models
  Query:    scenario_id?, model_type?
  Response: list[CausalDAG]
  동작: 저장된 인과 모형 목록 조회

GET  /api/causal/models/{model_id}
  Response: CausalDAG
  동작: 단일 인과 모형 조회

POST /api/causal/collect
  Request:  { scenario_id: str, result_id: str }
  Response: { observations_count: int }
  동작: 시뮬레이션 결과에서 인과 관측치 수집. 파이프라인 완료 후 자동 호출도 가능
```

### 3.7 SimulationOrchestrator 통합

파이프라인 완료 후 자동으로 인과 관측치를 수집한다:

```python
# simulation_orchestrator.py의 run_pipeline() 마지막 단계에 추가

# Stage 10: 인과 로그 수집 (선택적, 실패해도 파이프라인 성공)
try:
    collector = CausalLogCollector()
    await collector.collect_from_result(scenario_id, result_id)
except Exception as exc:
    logger.warning("[%s] Causal log collection failed (non-fatal): %s", scenario_id, exc)
```

### 3.8 수정 대상 파일

```
# 신규
backend/app/causal/__init__.py
backend/app/causal/domain_dag.py                    # 도메인 DAG 생성기
backend/app/causal/structure_learner.py              # pgmpy 구조 학습
backend/app/causal/models.py                         # Pydantic 모델
backend/app/services/causal_log_collector.py         # 시뮬레이션 로그 수집
backend/app/routers/causal.py                        # API 엔드포인트

# 수정
backend/app/database.py                              # causal_models, causal_observations 테이블
backend/app/services/simulation_orchestrator.py      # 파이프라인 완료 후 로그 수집 호출
backend/app/main.py                                  # causal 라우터 등록
```

---

## 4. 마일스톤

- [ ] **M1: 도메인 DAG 공식화** — `PROPAGATION_RULES`/`CASCADE_RULES`/결정 규칙을 NetworkX DiGraph로 변환. `build_domain_dag()` 함수. DAG 순환 검증.
  - 검증: `nx.is_directed_acyclic_graph(G)` 통과. `GET /api/causal/domain_dag` 응답에 노드/엣지 정확히 반환

- [ ] **M2: 시뮬레이션 로그 수집 파이프라인** — `CausalLogCollector`: 시뮬레이션 결과 + 지정학 이벤트에서 라운드별 상태 변수 추출 → `causal_observations` 테이블 저장. `SimulationOrchestrator.run_pipeline()` 완료 후 자동 수집.
  - 검증: 시뮬레이션 실행 완료 후 `causal_observations`에 `max_rounds`개 행 생성 확인

- [ ] **M3: pgmpy 구조 학습** — `CausalStructureLearner`: HillClimb + BDeu + 부트스트랩 50회. 70%+ 안정 엣지만 유지. 도메인 DAG와 비교 (confirmed/discovered/missing/reversed).
  - 검증: 100+ 관측치로 `POST /api/causal/learn` 호출 → 학습 DAG 반환 + 도메인 비교 결과에 confirmed 엣지 존재

- [ ] **M4: DAG 저장소 + API** — `causal_models` 테이블 CRUD. 도메인/학습/병합 모형 관리. 모형 목록/상세 조회 API.
  - 검증: 도메인 DAG 저장 → 조회. 학습 DAG 저장 → 도메인과 병합 → 병합 DAG 조회

---

## 5. 성공 기준

- 지정학 엔진의 기존 규칙이 공식 인과 DAG(NetworkX DiGraph)로 표현되고 API로 조회 가능하다
- 시뮬레이션 완료 시 라운드별 상태 변수가 자동 수집된다
- 100+ 관측치 축적 시 데이터 기반 인과 구조를 학습하고 도메인 DAG와 비교할 수 있다
- 학습된 DAG에서 도메인 DAG와 일치하는 엣지(confirmed)가 50% 이상이다

---

## 6. 위험 및 완화

| 위험 | 완화 |
|------|------|
| 100+ 런 축적까지 구조 학습 불가 | 도메인 DAG만으로 V8-2 진행 가능. 최소 데이터 가드레일로 422 반환 |
| 이산화로 연속 상태 변수 정밀도 손실 | KBinsDiscretizer의 bin 수 조정 가능 (기본 5). 민감도 분석 추가 |
| 시뮬레이션 로그 형식이 MiroFish 버전에 따라 변동 | 로그 파서에 포맷 감지 로직 + 폴백 |
| 도메인 DAG와 학습 DAG 충돌 시 판단 기준 | 기본: 도메인 우선 (domain_priority=True). 분석관이 API에서 선택 가능 |

---

## 진행 로그

| 날짜 | 상태 | 내용 |
|------|------|------|
| 2026-03-29 | Draft | V5 SPEC 기반 PRD 작성. 도메인 DAG 공식화 + 시뮬레이션 로그 수집 + pgmpy 구조 학습 설계. |
