# v13 SPEC: 서브그래프 분리 + 지정학 이벤트 HIT

> Status: Completed
> Created: 2026-04-07
> Completed: 2026-04-07
> Version: v13.0
> Dependencies: v12 (Simulation Service, LangGraph StateGraph, DecisionEngine, SSE)
> PRDs: [prd-1-subgraph-restructure](prds/prd-1-subgraph-restructure.md), [prd-2-geoevent-hit](prds/prd-2-geoevent-hit.md), [prd-3-frontend-integration](prds/prd-3-frontend-integration.md)

---

## 1. 문제 정의

### 1.1 현재 구조의 문제

현재 시뮬레이션 그래프는 **단일 플랫 StateGraph**다. 셋업 단계(분석→관계→행위자→설정)와 시뮬레이션 루프(라운드→결과→개입→결정)가 같은 레벨에 공존한다.

```
현재 (플랫 그래프):
START → analyze → build_relations → create_actors → configure
      → run_round → calculate_results → check_intervention ─┐
           ↑           apply_decision ◄──────────────────────┤
           ↑──── continue ◄──────────────────────────────────┤
                  generate_report ◄── complete ──────────────┘
                       → END
```

**문제점:**
1. **셋업과 시뮬레이션 루프의 관심사 혼재** — 9개 노드가 한 그래프에 평탄하게 나열
2. **HIT 트리거가 제한적** — 방향 체크포인트(N라운드마다)와 긴장도 임계값(0.6)만 사용. DecisionEngine이 매 라운드 생성하는 캐스케이드 이벤트(연쇄 반응)는 HIT를 트리거하지 않음
3. **지정학 이벤트에 대한 사용자 반응 기회 부재** — `military_movement` → `military_exercise` 연쇄가 발생해도 자동으로 다음 라운드 진행

### 1.2 목표

| # | 목표 | 검증 기준 |
|---|------|----------|
| G1 | 셋업과 시뮬레이션 루프를 서브그래프로 분리 | `builder.py`에서 부모 그래프가 서브그래프를 노드로 호출 |
| G2 | 지정학 이벤트 발생 시 HIT interrupt | 캐스케이드 이벤트, 고강도 군사 행동 시 `interrupt()` 호출되어 프론트에 DecisionCard 표시 |
| G3 | 프론트엔드에서 이벤트 트리거 맥락 표시 | DecisionCard에 "어떤 지정학 이벤트가 HIT를 트리거했는지" 표시 |
| G4 | 기존 auto 모드 호환 | `wargame_enabled: false` 시 현재 동작과 100% 동일 |

### 1.3 제약 조건

- LangGraph >= 0.3 (서브그래프 지원 확인됨, `pyproject.toml` 참조)
- `interrupt()`는 서브그래프 내부에서 사용 가능 — LangGraph가 부모 그래프로 전파
- 기존 `AsyncPostgresSaver` 체크포인터는 서브그래프 상태도 자동 저장
- SSE 파이프라인 (`pg_notify → simulation_stream.py → EventSource`) 변경 최소화

---

## 2. 아키텍처 설계

### 2.1 그래프 구조 변경

```
부모 그래프 (setup + orchestration):
START → analyze_situation → build_relations → create_actors → configure_sim
      → [simulation_loop 서브그래프] → generate_report → END

시뮬레이션 서브그래프 (round loop + HIT):
START → run_round → calculate_results → evaluate_events ─────┐
           ↑                                                  │
           ├──── continue (이벤트 미발생 & 라운드 잔여) ◄──────┤
           ├──── apply_decision ◄── interrupt() HIT ◄─────────┤
           └                                                  │
                END ◄── complete (라운드 소진) ────────────────┘
```

### 2.2 State 변경

```python
# 기존 SimulationState에 추가
class SimulationState(TypedDict):
    # ... 기존 필드 유지 ...

    # v13 추가
    round_events: list[dict]        # 현재 라운드에서 발생한 지정학 이벤트
    round_cascades: list[dict]      # 현재 라운드에서 발생한 캐스케이드 이벤트
    hit_trigger: dict | None        # HIT를 트리거한 이벤트 정보 (프론트 전달용)
```

### 2.3 HIT 트리거 기준

`evaluate_events_node`에서 아래 조건을 순서대로 검사. **하나라도 충족하면 `interrupt()`**.

| 우선순위 | 트리거 | 조건 | interrupt payload의 `trigger` 값 |
|---------|--------|------|----------------------------------|
| 1 | 캐스케이드 발생 | `round_cascades` 길이 >= 1 | `cascade_reaction` |
| 2 | 고강도 군사 행동 | `round_events` 중 `military_movement`, `deploy_forces` 이벤트의 magnitude >= 0.7 | `high_intensity_military` |
| 3 | 긴장도 임계값 (기존) | max tension >= 0.6 | `tension_threshold_exceeded` |
| 4 | 방향 체크포인트 (기존) | `_is_direction_round()` | `direction_checkpoint` |

**HIT 미발생 조건:** 위 어느 것도 충족하지 않고, 라운드가 남아 있으면 `continue`.

### 2.4 interrupt() payload 형식

```python
{
    "id": "dp_{uuid12}",
    "round": current_round,
    "trigger": "cascade_reaction",           # 트리거 유형
    "trigger_detail": {                      # 트리거한 이벤트 상세
        "event_type": "military_exercise",
        "source_actor": "CHN",
        "target_actors": ["JPN", "TWN"],
        "magnitude": 0.6,
        "description": "Threatened actor responds with military exercise",
        "cascade_chain": [                   # 캐스케이드인 경우 연쇄 경로
            {"from": "military_movement", "to": "military_exercise", "depth": 1},
        ],
    },
    "actor_states_snapshot": { ... },        # 현재 행위자 상태
    "options": [                             # 기존 형식 유지
        {
            "action_type": "propose_negotiation",
            "target": "CHN",
            "intensity": "high",
            "description": "중국에 협상 제안",
            "estimated_effect": { "tension_delta": -0.1, "resource_cost": 0.02 },
        },
        ...
    ],
}
```

---

## 3. 백엔드 변경 상세

### 3.1 `builder.py` — 서브그래프 분리

**변경 전:**
```python
_builder = StateGraph(SimulationState)
_builder.add_node("analyze_situation", analyze_situation_node)
# ... 9개 노드 평탄 나열 ...
_builder.add_edge(START, "analyze_situation")
# ... 모든 엣지 동일 레벨 ...
```

**변경 후:**
```python
# --- 시뮬레이션 루프 서브그래프 ---
_sim_loop = StateGraph(SimulationState)
_sim_loop.add_node("run_round", run_round_node)
_sim_loop.add_node("calculate_results", calculate_results_node)
_sim_loop.add_node("evaluate_events", evaluate_events_node)
_sim_loop.add_node("apply_decision", apply_decision_node)

_sim_loop.add_edge(START, "run_round")
_sim_loop.add_edge("run_round", "calculate_results")
_sim_loop.add_edge("calculate_results", "evaluate_events")
_sim_loop.add_conditional_edges("evaluate_events", should_continue, {
    "continue": "run_round",
    "apply_decision": "apply_decision",
    "complete": END,
})
_sim_loop.add_edge("apply_decision", "run_round")

# --- 부모 그래프 ---
_builder = StateGraph(SimulationState)
_builder.add_node("analyze_situation", analyze_situation_node)
_builder.add_node("build_relations", build_relations_node)
_builder.add_node("create_actors", create_actors_node)
_builder.add_node("configure_sim", configure_sim_node)
_builder.add_node("simulation_loop", _sim_loop.compile())
_builder.add_node("generate_report", generate_report_node)

_builder.add_edge(START, "analyze_situation")
_builder.add_edge("analyze_situation", "build_relations")
_builder.add_edge("build_relations", "create_actors")
_builder.add_edge("create_actors", "configure_sim")
_builder.add_edge("configure_sim", "simulation_loop")
_builder.add_edge("simulation_loop", "generate_report")
_builder.add_edge("generate_report", END)
```

### 3.2 `calculate_results_node` — 라운드 이벤트 상태 노출

**현재:** `engine.run_single_round()` 결과의 cascade 이벤트를 DB에 저장만 하고 state에 반환하지 않음.

**변경:** `round_events`와 `round_cascades`를 state에 반환.

```python
async def calculate_results_node(state: SimulationState) -> dict:
    # ... 기존 코드 유지 ...
    result = engine.run_single_round(state["round_actions"])

    # v13: cascade 이벤트를 state에 노출
    round_events = [e.to_dict() for e in engine._event_log[old_log_len:]]
    round_cascades = result.get("cascade_events", [])

    return {
        # ... 기존 반환값 유지 ...
        "round_events": round_events,
        "round_cascades": round_cascades,
    }
```

### 3.3 `evaluate_events_node` — 지정학 이벤트 기반 HIT (신규)

`check_intervention_node`를 대체. 기존 로직(방향 체크포인트, 긴장도) + 지정학 이벤트 트리거 추가.

```python
from langgraph.types import interrupt

HIGH_INTENSITY_TYPES = {"military_movement", "deploy_forces", "cyber_operation"}
HIGH_INTENSITY_THRESHOLD = 0.7
TENSION_THRESHOLD = 0.6

async def evaluate_events_node(state: SimulationState) -> dict:
    if state["current_round"] >= state["max_rounds"]:
        return {"decision_point": None, "user_decision": None, "hit_trigger": None}

    round_cascades = state.get("round_cascades", [])
    round_events = state.get("round_events", [])

    # 트리거 1: 캐스케이드 발생
    if round_cascades:
        dp = _build_event_interrupt(state, "cascade_reaction", round_cascades[0])
        user_decision = interrupt(dp)
        return {"user_decision": user_decision, "decision_point": None, "hit_trigger": dp}

    # 트리거 2: 고강도 군사 행동
    for evt in round_events:
        if evt.get("event_type") in HIGH_INTENSITY_TYPES and evt.get("magnitude", 0) >= HIGH_INTENSITY_THRESHOLD:
            dp = _build_event_interrupt(state, "high_intensity_military", evt)
            user_decision = interrupt(dp)
            return {"user_decision": user_decision, "decision_point": None, "hit_trigger": dp}

    # 트리거 3: 긴장도 임계값 (기존)
    max_tension = max(state.get("tension_levels", {}).values(), default=0.0)
    if max_tension >= TENSION_THRESHOLD:
        dp = _build_tension_interrupt(state, max_tension)
        user_decision = interrupt(dp)
        return {"user_decision": user_decision, "decision_point": None, "hit_trigger": dp}

    # 트리거 4: 방향 체크포인트 (기존)
    if _is_direction_round(state["current_round"]):
        dp = _build_direction_interrupt(state["current_round"])
        user_decision = interrupt(dp)
        return {"user_decision": user_decision, "decision_point": None, "hit_trigger": dp}

    return {"decision_point": None, "user_decision": None, "hit_trigger": None}
```

### 3.4 `event_emitter.py` — 신규 SSE 이벤트

```python
async def emit_geopolitical_event(
    self, scenario_id: str, round_num: int,
    trigger_type: str, events: list[dict],
) -> None:
    """라운드 종료 후 발생한 지정학 이벤트를 프론트에 알림."""
    await self._emit({
        "type": "geopolitical_event",
        "scenario_id": scenario_id,
        "round": round_num,
        "trigger_type": trigger_type,
        "events": events[:5],  # 페이로드 제한
    })
```

### 3.5 `command_listener.py` — 변경 없음

기존 `_apply_decision` → `Command(resume=...)` 흐름이 서브그래프 내부의 `interrupt()`에도 동일하게 작동. LangGraph가 서브그래프 interrupt를 부모로 전파하므로 command_listener 코드 변경 불필요.

---

## 4. 프론트엔드 변경 상세

### 4.1 SSE 이벤트 수신 — `useSimulationStream.ts`

**추가 이벤트:** `geopolitical_event`

```typescript
// 타입 추가 (simulation-stream.ts)
interface GeopoliticalEventPayload {
  round: number;
  trigger_type: "cascade_reaction" | "high_intensity_military" | "tension_threshold_exceeded" | "direction_checkpoint";
  events: Array<{
    event_type: string;
    source_actor_id: string;
    target_actor_ids: string[];
    magnitude: number;
    description: string;
  }>;
}

// State 추가
interface SimulationStreamState {
  // ... 기존 필드 ...
  latestGeopoliticalEvent: GeopoliticalEventPayload | null;
}

// Reducer 추가
case "GEOPOLITICAL_EVENT":
  return {
    ...state,
    latestGeopoliticalEvent: action.payload,
  };
```

**SSE 리스너 추가:**
```typescript
es.addEventListener("geopolitical_event", (e) => {
  dispatch({ type: "GEOPOLITICAL_EVENT", payload: JSON.parse(e.data) });
});
```

### 4.2 `useSimulation.ts` — `attachStream` 상태 매핑

**현재:** `simulating` → `"simulating:running"` (워게임 모드에서도 동일)

**추가 매핑 불필요.** v13에서의 앞선 수정(`SimulationPanel.tsx`의 `wargamePhaseActive` 조건 확장)으로 `"simulating:running"` 상태에서도 WarRoom이 표시됨. `intervention_required` 이벤트는 기존과 동일하게 `"simulating:wargame:decision"`으로 매핑.

### 4.3 `DecisionCard.tsx` — 트리거 맥락 표시

**변경:** interrupt payload에 `trigger`와 `trigger_detail`이 포함되므로, DecisionCard 상단에 트리거 정보 표시.

```
┌─────────────────────────────────────────┐
│ ⚠️ 지정학 이벤트 대응              Round 5 │
│─────────────────────────────────────────│
│ 🔴 연쇄 반응 감지                         │
│ CHN → military_movement → JPN, TWN       │
│   → military_exercise (연쇄)             │
│─────────────────────────────────────────│
│ "남중국해에서 군사적 긴장이 고조되고        │
│  있습니다. 대응 방안을 결정하십시오."       │
│─────────────────────────────────────────│
│ [🗣️ 외교적 제안] [⚔️ 병력 배치] ...      │
└─────────────────────────────────────────┘
```

**데이터 흐름:**
1. `intervention_required` SSE → `useSimulationStream` → `streamState.decisionPoint`
2. `decisionPoint.trigger` 존재 시 → DecisionCard에 트리거 섹션 렌더링
3. `decisionPoint.trigger_detail.cascade_chain` 존재 시 → 연쇄 경로 시각화

### 4.4 `ContextPanel.tsx` — 이벤트 알림 배지

`geopolitical_event` SSE 수신 시 ContextPanel에 최근 이벤트 요약 배지 표시.

```
┌──────────────────┐
│ 상황판     결정 필요 │
│──────────────────│
│ 🔴 연쇄 이벤트 2건  │  ← 신규: 지정학 이벤트 배지
│ military_exercise │
│ diplomatic_statement│
│──────────────────│
│ 행위자 상태 (4)     │
│ [CHN] 위협 72%     │
│ [USA] 위협 45%     │
│ ...                │
└──────────────────┘
```

### 4.5 `FeedPanel.tsx` — 이벤트 하이라이트

`geopolitical_event` SSE 수신 시 FeedPanel의 액션 피드에 캐스케이드 이벤트를 시각적으로 강조 (빨간 테두리 + "연쇄" 뱃지).

---

## 5. 데이터 흐름 (End-to-End)

```
[Simulation Service]
  run_round_node
    → LLM 에이전트 행동 결정 → round_actions
    → emit_agent_action (SSE)
  
  calculate_results_node
    → DecisionEngine.run_single_round(round_actions)
    → round_events, round_cascades 생성
    → emit_round_complete (SSE)
    → emit_geopolitical_event (SSE) ← 신규
    → state에 round_events, round_cascades 저장

  evaluate_events_node
    → round_cascades 검사 → 캐스케이드 있으면 interrupt()
    → round_events 검사 → 고강도 군사 있으면 interrupt()
    → tension 검사 → 임계값 초과하면 interrupt()
    → direction 검사 → 체크포인트면 interrupt()
    → 모두 아니면 continue

  interrupt() 발생 시:
    → command_listener가 interrupt 감지
    → emit_intervention_required (SSE)
    → persist_intervention_decision_point (DB)

[Gateway]
  simulation_stream.py
    → pg_notify 수신 → SSE 전달 (변경 없음)

[Frontend]
  useSimulationStream
    → geopolitical_event 수신 → latestGeopoliticalEvent 업데이트
    → intervention_required 수신 → decisionPoint 업데이트 (기존)
  
  WarRoom
    → DecisionCard: trigger/trigger_detail 표시
    → ContextPanel: 이벤트 배지
    → FeedPanel: 캐스케이드 하이라이트
```

---

## 6. 마일스톤

### M1: 서브그래프 분리 (백엔드) ✅

**범위:** `builder.py` 리팩토링 + State 필드 추가 + 기존 동작 유지 확인
**PRD:** [prd-1-subgraph-restructure.md](prds/prd-1-subgraph-restructure.md)

| 파일 | 변경 |
|------|------|
| `simulation-service/app/graph/builder.py` | 서브그래프 분리 (재작성) |
| `simulation-service/app/graph/state.py` | `round_events`, `round_cascades`, `hit_trigger` 필드 추가 |
| `simulation-service/app/graph/nodes/results.py` | `round_events`, `round_cascades` state 반환 + `emit_geopolitical_event()` 호출 |
| `simulation-service/app/graph/nodes/configure.py` | 신규 필드 초기화 |
| `simulation-service/app/services/command_listener.py` | initial_state에 신규 필드 추가 |

### M2: 지정학 이벤트 HIT (백엔드) ✅

**범위:** `evaluate_events_node` 구현 + `check_intervention_node` 대체 + SSE 이벤트 추가
**PRD:** [prd-2-geoevent-hit.md](prds/prd-2-geoevent-hit.md)

| 파일 | 변경 |
|------|------|
| `simulation-service/app/graph/nodes/intervene.py` | `evaluate_events_node` 신규 (4단계 트리거 + 2라운드 쿨다운) |
| `simulation-service/app/graph/nodes/decision.py` | 결정 적용 후 이벤트 필드 초기화 |
| `simulation-service/app/services/event_emitter.py` | `emit_geopolitical_event()` 추가 |

### M3: 프론트엔드 통합 ✅

**범위:** SSE 이벤트 수신 + DecisionCard 트리거 표시 + ContextPanel/FeedPanel 이벤트 표시
**PRD:** [prd-3-frontend-integration.md](prds/prd-3-frontend-integration.md)

| 파일 | 변경 |
|------|------|
| `frontend/src/types/simulation-stream.ts` | `TriggerDetail`, `CascadeChainEntry`, `GeopoliticalEventPayload` 타입 + State 확장 |
| `frontend/src/hooks/useSimulationStream.ts` | `geopolitical_event` 리스너 + reducer + `latestGeopoliticalEvent` state |
| `frontend/src/components/wargame/DecisionCard.tsx` | `triggerInfo` prop + `TriggerBanner` 컴포넌트 (트리거 유형별 색상) |
| `frontend/src/components/wargame/ContextPanel.tsx` | `geopoliticalEvent` prop + 이벤트 배지 (dismissible) |
| `frontend/src/components/wargame/FeedPanel.tsx` | 캐스케이드 액션 빨간 보더 + "연쇄" 뱃지 |
| `frontend/src/components/wargame/WarRoom.tsx` | `triggerInfo`, `geopoliticalEvent` prop 전달 |

---

## 7. 리스크 및 지뢰

| 리스크 | 영향 | 대응 | 결과 |
|--------|------|------|------|
| LangGraph 서브그래프 내 `interrupt()`가 부모로 전파되지 않을 가능성 | 치명적 | LangGraph >= 0.3에서 서브그래프 interrupt 전파는 공식 지원 | ✅ 정상 동작 확인 |
| 캐스케이드가 매 라운드 발생하여 HIT가 너무 자주 트리거 | UX 저하 | 트리거 조건에 쿨다운 추가 (마지막 HIT 이후 최소 2라운드 경과 조건) | ✅ `HIT_COOLDOWN_ROUNDS=2` 구현 |
| `AsyncPostgresSaver`가 서브그래프 상태를 올바르게 직렬화하지 않을 가능성 | 치명적 | M1에서 기존 시나리오 재실행으로 체크포인터 호환성 검증 | ✅ 서브그래프는 체크포인터 없이 컴파일, 부모가 전체 관리 |
| `round_events`가 너무 커서 pg_notify 8KB 제한 초과 | SSE 전달 실패 | 기존 `event_emitter._emit()`의 `_PAYLOAD_LIMIT` + `event_ref` 로직이 이미 대응 | ✅ events[:5] 제한 + event_ref 폴백 |
| interrupt payload의 `trigger_detail` 형식이 기존 DecisionCard와 비호환 | 프론트 렌더링 실패 | `trigger`, `trigger_detail`은 optional 필드로 추가 — 기존 payload에 없으면 기존 렌더링 | ✅ optional prop + graceful fallback |

---

## 8. 변경하지 않는 것

- `command_listener.py` — LangGraph가 서브그래프 interrupt를 부모로 전파하므로 로직 변경 불필요 (initial_state 필드만 추가)
- `simulation_stream.py` (Gateway SSE) — 이벤트 타입 기반 라우팅이므로 신규 `geopolitical_event`도 자동 전달
- `simulation_v2.py` (Gateway API) — `start_v2`, `decide_v2` 엔드포인트 변경 없음
- `DecisionEngine` (`engine/`) — 엔진 로직 자체는 변경 없음. 이미 cascade 이벤트를 생성하고 있음
- `useSimulation.ts` — `attachStream`의 `intervention_required` 핸들러 변경 없음
