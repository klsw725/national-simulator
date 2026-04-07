# PRD-1: 서브그래프 분리

> Phase: 1 / 3
> Status: Completed
> 선행 조건: v12 완료 (Simulation Service, LangGraph StateGraph, DecisionEngine)
> 참조: v13-spec.md §2.1 (그래프 구조), §3.1 (builder.py)

---

## 목표

단일 플랫 StateGraph를 **부모 그래프(셋업) + 시뮬레이션 서브그래프(라운드 루프)**로 분리한다. 기존 동작을 100% 유지하면서 구조적 관심사를 분리.

**이 Phase가 끝나면**: 그래프가 2레벨 계층으로 동작. 셋업 노드(analyze→relations→actors→configure)는 부모, 시뮬레이션 루프(run_round→results→evaluate→decision)는 서브그래프. interrupt/resume은 LangGraph 서브그래프 전파로 동작.

---

## M1: SimulationState 확장

### 작업

1. `simulation-service/app/graph/state.py` — 3개 필드 추가:
   - `round_events: list[dict]` — 현재 라운드에서 발생한 지정학 이벤트
   - `round_cascades: list[dict]` — 현재 라운드에서 발생한 캐스케이드 이벤트
   - `hit_trigger: dict | None` — HIT를 트리거한 이벤트 정보

2. `simulation-service/app/graph/nodes/configure.py` — 신규 필드 초기화:
   - `round_events: []`, `round_cascades: []`, `hit_trigger: None`

3. `simulation-service/app/services/command_listener.py` — `initial_state`에 신규 필드 추가

### 결과물

| 파일 | 상태 |
|------|------|
| `simulation-service/app/graph/state.py` | 수정 |
| `simulation-service/app/graph/nodes/configure.py` | 수정 |
| `simulation-service/app/services/command_listener.py` | 수정 |

### 성공 기준

- 기존 시나리오 생성/실행 시 initial_state 오류 없음
- TypedDict 검증 통과

---

## M2: calculate_results_node 이벤트 노출

### 작업

1. `simulation-service/app/graph/nodes/results.py` 수정:
   - `engine.run_single_round()` 반환값에서 `cascade_events` 추출
   - `engine._event_log`에서 신규 이벤트 추출
   - state 반환에 `round_events`, `round_cascades` 추가
   - `emit_geopolitical_event()` 호출 (이벤트 또는 캐스케이드 발생 시)

### 결과물

| 파일 | 상태 |
|------|------|
| `simulation-service/app/graph/nodes/results.py` | 수정 |

### 성공 기준

- 라운드 실행 후 state에 `round_events`, `round_cascades`가 올바르게 채워짐
- 이벤트 발생 시 SSE `geopolitical_event` 발행

---

## M3: builder.py 서브그래프 구조

### 작업

1. `simulation-service/app/graph/builder.py` 전체 재작성:

```
부모 그래프:
  START → analyze_situation → build_relations → create_actors
        → configure_sim → [simulation_loop 서브그래프] → generate_report → END

시뮬레이션 서브그래프:
  START → run_round → calculate_results → evaluate_events
        → conditional: continue|apply_decision|complete
        → END
```

2. 서브그래프는 `_sim_loop.compile()` (체크포인터 없음)로 컴파일
3. 부모 그래프에 `_builder.add_node("simulation_loop", _sim_loop.compile())`로 등록
4. 부모 그래프만 `AsyncPostgresSaver` 체크포인터 사용
5. import 변경: `check_intervention_node` → `evaluate_events_node`

### 결과물

| 파일 | 상태 |
|------|------|
| `simulation-service/app/graph/builder.py` | 재작성 |

### 성공 기준

- `get_graph()` 호출 시 오류 없이 컴파일
- 시뮬레이션 실행 시 셋업 → 서브그래프 → 보고서 순서로 정상 동작
- interrupt()가 서브그래프에서 부모로 전파되어 command_listener에서 감지
- Docker 컨테이너 재시작 후 정상 기동

---

## 구현 메모

- LangGraph >= 0.3에서 서브그래프 내 `interrupt()`는 자동으로 부모 그래프로 전파
- `AsyncPostgresSaver`는 서브그래프 상태를 부모 그래프의 체크포인터에 포함하여 직렬화
- `command_listener.py`의 `_apply_decision`은 `Command(resume=...)` 사용 — 서브그래프 interrupt에도 동일하게 작동하므로 변경 불필요
