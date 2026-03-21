# PRD: 지정학 엔진 ↔ 시뮬레이션 통합

> Status: Draft
> Created: 2026-03-21
> Dependencies: v2-geopolitics-scenario-engine, v2-pipeline-checkpoints, v3-simulation-params, v3-intelligent-seed
> 관련 스펙: `specs/V3-SPEC.md` PRD V3-1
> 버전: v3.0

---

## 1. 문제 정의

DecisionEngine은 독립 API (`POST /api/geopolitics/simulate`)로만 동작하고, 시뮬레이션 파이프라인과 완전히 분리되어 있다.

현재 상태:
- **DecisionEngine** (`geopolitics/engine.py`): 규칙 기반 지정학 의사결정 엔진. 독립 실행만 가능. SimulationOrchestrator와 무연결.
- **GeopoliticsMapper** (`services/geopolitics_mapper.py`): 소셜 액션 → 지정학 카테고리 레이블링만 수행. DecisionEngine을 호출하지 않음.
- **geopolitics_events 테이블** (`database.py:113-124`): 스키마 정의됨. **기록하는 코드 없음**.
- **체크포인트 파이프라인**: CP1(seed) → CP2(ontology) → CP3(graph) → CP4(profiles) → CP5(config). **지정학 검토 단계 없음**.

결과: 시뮬레이션 결과가 지정학적으로 분석되지 않고, 연쇄 이벤트 분석이 수행되지 않으며, 지정학 이벤트가 DB에 저장되지 않는다.

## 2. 솔루션 개요

- **SimulationOrchestrator → DecisionEngine 브릿지** — 시뮬레이션 완료 후 에이전트 행동을 GeopoliticsEvent로 변환하여 DecisionEngine에 주입
- **geopolitics_events DB 저장** — DecisionEngine 분석 결과를 geopolitics_events 테이블에 영구 저장
- **CP6 지정학 검토 체크포인트** — 체크포인트 파이프라인에 지정학 분석 검토 단계 추가
- **프론트엔드 지정학 분석 뷰** — 시뮬레이션 결과 패널에 지정학 분석 탭 통합

## 3. 기술 상세

### 3.1 SimulationOrchestrator → DecisionEngine 브릿지

시뮬레이션 완료 후 (Step 5 이후, Step 6 이전) DecisionEngine에 결과를 주입하는 브릿지 단계를 추가한다.

```python
# simulation_orchestrator.py에 추가
async def _step_geopolitics_analysis(
    self, scenario_id: str, simulation_result_id: str, actions: list[dict]
) -> dict:
    """
    1. GeopoliticsMapper로 소셜 액션 → 지정학 카테고리 변환
    2. 시뮬레이션 에이전트를 GeopoliticalActorState로 매핑
    3. DecisionEngine.run_simulation()으로 연쇄 분석 실행
    4. 결과를 geopolitics_events 테이블에 저장
    """
```

변환 흐름:
```
MiroFish 시뮬레이션 액션
  ↓ GeopoliticsMapper (create_post → diplomatic_statement 등)
지정학 카테고리 액션
  ↓ ActorMapper (에이전트 → GeopoliticalActorState)
GeopoliticsEvent 리스트
  ↓ DecisionEngine.run_simulation()
연쇄 분석 결과 (cascade events + state changes)
  ↓ 저장
geopolitics_events 테이블
```

### 3.2 액션 → GeopoliticsEvent 변환

```python
def actions_to_geopolitics_events(
    actions: list[dict], actor_mapping: dict[str, str]
) -> list[GeopoliticsEvent]:
    """
    시뮬레이션 액션을 GeopoliticsEvent로 변환.
    
    actor_mapping: 시뮬레이션 에이전트 ID → GeopoliticalActorState.actor_id
    기존 GeopoliticsMapper의 ACTION_TO_GEOPOLITICS 매핑 활용:
      create_post → diplomatic_statement
      quote_post → official_response
      repost → alliance_support
      like_post → tacit_approval
      follow → diplomatic_engagement
      do_nothing → strategic_observation
    """
```

### 3.3 geopolitics_events DB 저장

기존 테이블 스키마 (`database.py:113-124`)를 그대로 활용:

```sql
-- 이미 정의된 테이블 (현재 미사용)
CREATE TABLE geopolitics_events (
    id TEXT PRIMARY KEY,
    scenario_id TEXT NOT NULL,
    simulation_result_id TEXT NOT NULL,
    action_type TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    target_actor_ids TEXT,
    content TEXT,
    magnitude REAL,
    round_number INTEGER,
    event_at TEXT NOT NULL
);
```

추가 API 엔드포인트:

```
GET /api/scenario/{id}/geopolitics          → 지정학 분석 결과 요약
GET /api/scenario/{id}/geopolitics/events   → 이벤트 목록 (페이지네이션)
GET /api/scenario/{id}/geopolitics/actors   → 행위자 최종 상태
GET /api/scenario/{id}/geopolitics/timeline → 라운드별 이벤트 타임라인
```

### 3.4 CP6 지정학 검토 체크포인트

체크포인트 모드에서 지정학 분석 결과를 검토하는 단계를 추가한다.

```python
# simulation.py CHECKPOINT_STEPS에 추가
"checkpoint:geopolitics": {
    "step": 6,
    "label": "지정학 분석",
    "editable": False,  # 읽기 전용 (분석 결과 검토만)
    "description": "시뮬레이션 결과의 지정학적 분석 결과를 검토합니다"
}
```

파이프라인 상태 흐름 변경:
```
기존: simulating:running → simulating:report → completed
변경: simulating:running → simulating:geopolitics → simulating:report → completed
```

### 3.5 프론트엔드 지정학 분석 뷰

SimulationPanel에 "지정학" 탭 추가 (completed 상태에서 표시):

- **이벤트 타임라인**: 라운드별 지정학 이벤트 (action_type, actor, magnitude)
- **행위자 상태 요약**: 각 행위자의 최종 threat_perception, domestic_pressure, resource_level
- **연쇄 분석 시각화**: cascade event 트리 (원본 이벤트 → 연쇄 이벤트)

### 3.6 수정 대상 파일

```
backend/app/services/simulation_orchestrator.py  # _step_geopolitics_analysis 추가
backend/app/services/geopolitics_mapper.py       # actions_to_geopolitics_events 확장
backend/app/geopolitics/engine.py                # 시뮬레이션 결과 기반 실행 모드 추가
backend/app/routers/simulation.py                # CP6 + 지정학 API 엔드포인트
backend/app/routers/scenario.py                  # 지정학 결과 조회 API
frontend/src/components/simulation/SimulationPanel.tsx    # "지정학" 탭 추가
frontend/src/components/simulation/GeopoliticsView.tsx    # 신규: 지정학 분석 뷰
frontend/src/components/simulation/PipelineProgress.tsx   # Step 7 추가 (지정학)
frontend/src/types/simulation.ts                          # GeopoliticsEvent 타입
frontend/src/lib/gatewayApi.ts                            # 지정학 API 호출
```

## 4. 마일스톤

- [ ] **M1: SimulationOrchestrator → DecisionEngine 브릿지** — 시뮬레이션 액션을 GeopoliticsEvent로 변환하는 브릿지 로직 구현. 에이전트 → GeopoliticalActorState 매핑. DecisionEngine.run_simulation() 호출.
  - 검증: 시뮬레이션 완료 후 DecisionEngine이 연쇄 분석을 수행하고 결과 반환

- [ ] **M2: DecisionEngine 결과 → geopolitics_events DB 저장 + API** — 분석 결과를 geopolitics_events 테이블에 저장. 조회 API (events, actors, timeline) 구현.
  - 검증: GET /api/scenario/{id}/geopolitics/events에서 저장된 이벤트 조회 가능

- [ ] **M3: CP6 지정학 검토 체크포인트 추가** — 체크포인트 파이프라인에 geopolitics 단계 추가. PipelineProgress에 Step 7 표시. 체크포인트 모드에서 검토 가능.
  - 검증: checkpoint 모드에서 지정학 분석 단계에 일시정지. 결과 확인 후 계속.

- [ ] **M4: 프론트엔드 지정학 분석 뷰** — SimulationPanel에 "지정학" 탭 추가. 이벤트 타임라인, 행위자 상태, 연쇄 분석 표시. geopolitics_enabled=true인 시나리오에서만 표시.
  - 검증: 시뮬레이션 완료 후 "지정학" 탭에서 분석 결과 확인 가능

## 5. 성공 기준

- 시뮬레이션 결과가 DecisionEngine에 자동 주입되어 연쇄 분석이 수행된다
- 지정학 분석 결과가 geopolitics_events 테이블에 영구 저장된다
- 체크포인트 모드에서 지정학 분석 결과를 검토할 수 있다
- 프론트엔드에서 지정학 이벤트 타임라인과 행위자 상태를 조회할 수 있다
- geopolitics_enabled=false인 시나리오에서는 지정학 분석이 스킵된다

## 6. 위험 및 완화

| 위험 | 완화 |
|------|------|
| 시뮬레이션 에이전트 → 지정학 행위자 매핑이 부정확 | 온톨로지의 entity_type 기반 자동 매핑 + 수동 매핑 폴백 |
| DecisionEngine 규칙이 시뮬레이션 결과와 맞지 않음 | 기존 규칙 기반 엔진 사용. LLM 기반 분석은 향후 확장 |
| 연쇄 분석이 과도한 이벤트 생성 | max_cascade_depth=3, decay=0.7 기존 제한 유지 |
| geopolitics 단계 추가로 파이프라인 시간 증가 | DecisionEngine은 LLM 미사용 (규칙 기반). 수 초 내 완료 |

## 7. 참고

### 관련 PRD
- **v2-geopolitics-scenario-engine** — DecisionEngine, GeopoliticalActorState 구현
- **v2-pipeline-checkpoints** — 체크포인트 시스템 (CP1-CP5)
- **v3-simulation-params (V3-3)** — geopolitics_enabled 토글 (의존)
- **v3-oasis-runtime (V3-6)** — GeopoliticsPlatform 통합 테스트 (후속)

### 현재 DecisionEngine 아키텍처
- 규칙 기반 의사결정: threat_escalation=0.6, resource_crisis=0.3, pressure_revolt=0.8
- 연쇄 규칙: max_cascade_depth=3, decay=0.7
- 12개 액션 타입: diplomatic_statement, military_movement, sanction_impose 등
- 입력: GeopoliticalActorState 리스트 + rounds
- 출력: timeline (events, cascade events, state changes, final states)

## 진행 로그

| 날짜 | 상태 | 내용 |
|------|------|------|
| 2026-03-21 | Draft | V3-1 지정학 엔진 ↔ 시뮬레이션 통합 PRD 초안 작성 |
