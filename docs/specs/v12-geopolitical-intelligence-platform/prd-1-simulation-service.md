# PRD-1: Simulation Service 골격

> Phase: 1 / 4
> 예상 기간: 2주
> 선행 조건: PRD-0 완료 (온톨로지 스키마, pg_notify, SSE 브릿지)
> 참조: v12-spec.md §3 (아키텍처), §5 (LangGraph), §6 (통신)

---

## 목표

MiroFish를 대체하는 **Simulation Service**를 독립 서비스로 구축한다. LangGraph StateGraph 골격, PostgreSQL NOTIFY 발행/수신, 체크포인터를 설정하고, Gateway와 연동한다. 에이전트는 아직 stub — "do_nothing"을 반환.

**이 Phase가 끝나면**: 시나리오 생성 → Simulation Service가 파이프라인 실행 → Gateway가 SSE로 진행 상황 전달 → 프론트엔드에서 확인 가능. (에이전트 로직은 Phase 2)

---

## M1: 서비스 부트스트랩

### 작업

1. `simulation-service/` 디렉토리 생성 (프로젝트 루트):

```
simulation-service/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI 앱
│   ├── config.py             # 환경 변수 (DB_URL, LLM_API 등)
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── state.py          # SimulationState TypedDict
│   │   ├── builder.py        # StateGraph 정의
│   │   └── nodes/
│   │       ├── __init__.py
│   │       ├── analyze.py    # analyze_situation 노드
│   │       ├── relations.py  # build_relations 노드
│   │       ├── actors.py     # create_actors 노드
│   │       ├── configure.py  # configure_sim 노드
│   │       ├── round.py      # run_round 노드
│   │       ├── results.py    # calculate_results 노드
│   │       ├── intervene.py  # check_intervention 노드
│   │       ├── decision.py   # apply_decision 노드
│   │       └── report.py     # generate_report 노드
│   ├── services/
│   │   ├── __init__.py
│   │   ├── command_listener.py  # sim_commands LISTEN
│   │   └── event_emitter.py     # sim_events NOTIFY 래퍼
│   └── ontology/
│       └── __init__.py          # backend/app/ontology에서 필요한 것만 임포트
├── pyproject.toml
├── Dockerfile
└── README.md
```

2. `pyproject.toml` — 의존성:
   - `fastapi`, `uvicorn`
   - `langgraph`, `langchain-core`, `langchain-openai` (또는 `langchain-community` for OpenAI-compatible)
   - `langgraph-checkpoint-postgres`
   - `asyncpg`
   - `httpx` (ShadowBroker 호출용)

3. `docker-compose.yml` 수정 — `simulation-service` 추가:
   - 포트: 5001 (기존 MiroFish와 동일, 추후 MiroFish 제거 시 충돌 없음)
   - 환경 변수: DATABASE_URL, LLM_API_BASE, LLM_API_KEY, LLM_MODEL, SHADOWBROKER_URL
   - 의존: postgres, dozerdb

4. ⚠️ LLM 설정 주의 (AGENTS.md 지뢰): OpenAI Compatible API 가정. litellm/OpenRouter 등 프로바이더 교체 가능. 특정 프로바이더 고유 기능(structured output 등) 의존 금지.

### 결과물

| 파일 | 상태 |
|---|---|
| `simulation-service/` (전체 디렉토리) | 신규 |
| `docker-compose.yml` | 수정 |

### 성공 기준

- `docker compose up simulation-service` → 정상 기동
- `GET /health` → 200 OK
- PostgreSQL 연결 확인

---

## M2: LangGraph StateGraph 골격

### 작업

1. `simulation-service/app/graph/state.py` — SimulationState 정의:

```python
class SimulationState(TypedDict):
    scenario_id: str
    seed_text: str
    ontology_version: str
    graph_id: str
    situation_summary: str
    actors: dict[str, dict]           # nation_code → profile
    actor_states: dict[str, dict]     # nation_code → GeopoliticalActorState 직렬화
    current_round: int
    max_rounds: int
    round_actions: list[dict]
    action_history: list[dict]
    tension_levels: dict[str, float]
    decision_engine_state: dict
    decision_point: dict | None
    user_decision: dict | None
    phase: str                        # analyzing | building | configuring | simulating | reporting
    status: str                       # running | paused | completed | failed
```

2. `simulation-service/app/graph/builder.py` — StateGraph 정의:

```python
builder = StateGraph(SimulationState)

# 파이프라인 노드 (순차)
builder.add_node("analyze_situation", analyze_situation_node)
builder.add_node("build_relations", build_relations_node)
builder.add_node("create_actors", create_actors_node)
builder.add_node("configure_sim", configure_sim_node)

# 시뮬레이션 루프 노드 (순환)
builder.add_node("run_round", run_round_node)
builder.add_node("calculate_results", calculate_results_node)
builder.add_node("check_intervention", check_intervention_node)
builder.add_node("apply_decision", apply_decision_node)

# 완료 노드
builder.add_node("generate_report", generate_report_node)

# 엣지: 파이프라인
builder.add_edge(START, "analyze_situation")
builder.add_edge("analyze_situation", "build_relations")
builder.add_edge("build_relations", "create_actors")
builder.add_edge("create_actors", "configure_sim")
builder.add_edge("configure_sim", "run_round")

# 엣지: 시뮬레이션 루프
builder.add_edge("run_round", "calculate_results")
builder.add_edge("calculate_results", "check_intervention")
builder.add_conditional_edges("check_intervention", should_continue, {
    "continue": "run_round",
    "interrupt": END,             # LangGraph interrupt — resume 시 apply_decision으로
    "complete": "generate_report",
})
builder.add_edge("apply_decision", "run_round")
builder.add_edge("generate_report", END)
```

3. 모든 노드는 **stub 구현**:
   - `analyze_situation`: seed_text를 situation_summary에 복사
   - `build_relations`: graph_id를 "stub_graph"로 설정
   - `create_actors`: 빈 actors dict
   - `configure_sim`: max_rounds 설정
   - `run_round`: round_actions = [{"actor": "stub", "action_type": "do_nothing"}]
   - `calculate_results`: current_round += 1
   - `check_intervention`: current_round >= max_rounds면 "complete"
   - `generate_report`: "Stub report"

### 결과물

| 파일 | 상태 |
|---|---|
| `simulation-service/app/graph/state.py` | 신규 |
| `simulation-service/app/graph/builder.py` | 신규 |
| `simulation-service/app/graph/nodes/*.py` (9개) | 신규 (stub) |

### 성공 기준

- `graph.ainvoke({"scenario_id": "test", "seed_text": "...", "max_rounds": 3})` 실행 시 3라운드 순환 후 보고서 노드에서 종료
- 체크포인트가 PostgreSQL에 저장됨 확인

---

## M3: 체크포인터 설정

### 작업

1. `simulation-service/app/graph/builder.py`에서 체크포인터 연결:

```python
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

async def get_graph():
    checkpointer = AsyncPostgresSaver.from_conn_string(settings.DATABASE_URL)
    await checkpointer.setup()   # 테이블 자동 생성

    return builder.compile(
        checkpointer=checkpointer,
        interrupt_before=["check_intervention"],
    )
```

2. 시뮬레이션 실행 시 `thread_id` = `scenario_id` 사용하여 시나리오별 독립 체크포인트.

3. What-if 분기 지원: `thread_id`를 복제하여 새 브랜치 생성하는 유틸리티 함수.

### 결과물

| 파일 | 상태 |
|---|---|
| `simulation-service/app/graph/builder.py` | 수정 |

### 성공 기준

- 시뮬레이션 중간에 서비스 재시작 후 `graph.aget_state(config)` → 마지막 체크포인트에서 상태 복원
- `interrupt_before=["check_intervention"]` 동작: 해당 노드 직전에 실행 일시정지

---

## M4: NOTIFY 이벤트 발행

### 작업

1. `simulation-service/app/services/event_emitter.py` — 각 노드에서 NOTIFY 발행:

```python
class SimulationEventEmitter:
    """LangGraph 노드 실행 시 pg_notify로 이벤트 발행."""

    async def emit_phase_change(self, scenario_id: str, phase: str, progress: float)
    async def emit_round_complete(self, scenario_id: str, round: int, actions: list, tension: float)
    async def emit_agent_action(self, scenario_id: str, round: int, action: dict)
    async def emit_intervention_required(self, scenario_id: str, decision_point: dict)
    async def emit_report_ready(self, scenario_id: str, report_id: str)
    async def emit_error(self, scenario_id: str, error: str)
```

2. 각 stub 노드에 emitter 호출 추가:
   - `analyze_situation` 시작/완료 → `phase_change(analyzing, 0/100)`
   - `run_round` 완료 → `round_complete`
   - `check_intervention`에서 interrupt → `intervention_required`

3. PRD-0의 `pg_event_bus.emit_event` 재사용. Simulation Service에서 직접 `asyncpg`로 NOTIFY.

### 결과물

| 파일 | 상태 |
|---|---|
| `simulation-service/app/services/event_emitter.py` | 신규 |
| `simulation-service/app/graph/nodes/*.py` | 수정 (emitter 호출 추가) |

### 성공 기준

- 시뮬레이션 실행 시 Gateway의 `/api/scenario/{id}/stream` SSE에서 `phase_change`, `round_complete` 이벤트 수신
- 이벤트 지연: NOTIFY → Gateway SSE < 100ms

---

## M5: 명령 수신 (sim_commands LISTEN)

### 작업

1. `simulation-service/app/services/command_listener.py`:

```python
class SimulationCommandListener:
    """sim_commands 채널 LISTEN. 수신된 명령에 따라 시뮬레이션 제어."""

    async def start(self):
        """백그라운드 태스크로 LISTEN 시작."""

    async def handle_command(self, command: dict):
        """명령 유형별 처리:
        - start_simulation: LangGraph graph.ainvoke 시작
        - stop_simulation: 실행 중인 그래프 취소
        - user_decision: LangGraph resume with user_input
        """
```

2. `simulation-service/app/main.py`에서 lifespan으로 listener 시작:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    listener = SimulationCommandListener()
    task = asyncio.create_task(listener.start())
    yield
    task.cancel()
```

3. 명령 유형:
   - `start_simulation`: scenario_id, seed_text, max_rounds → graph.ainvoke
   - `stop_simulation`: scenario_id → 실행 취소
   - `user_decision`: scenario_id, decision → graph.aupdate_state + resume

### 결과물

| 파일 | 상태 |
|---|---|
| `simulation-service/app/services/command_listener.py` | 신규 |
| `simulation-service/app/main.py` | 수정 |

### 성공 기준

- Gateway에서 `pg_notify('sim_commands', '{"type":"start_simulation",...}')` 실행 시 Simulation Service가 LangGraph 실행 시작
- 실행 중 `stop_simulation` 명령으로 중단 가능

---

## M6: Gateway 연동

### 배경

현재 Gateway는 `MiroFishClient`로 MiroFish HTTP API를 호출한다. 이를 `pg_notify`로 대체한다. 기존 라우터를 수정하지 않고, 새 라우터를 추가하여 점진적 전환.

### 작업

1. `backend/app/routers/simulation_v2.py` 신규 생성:

```python
@router.post("/api/scenario/{scenario_id}/start_v2")
async def start_simulation_v2(scenario_id: str, body: StartSimulationRequest):
    """Simulation Service에 시뮬레이션 시작 명령 전송.
    MiroFishClient 대신 pg_notify 사용."""
    await emit_command("sim_commands", {
        "type": "start_simulation",
        "scenario_id": scenario_id,
        "seed_text": body.seed_text,
        "max_rounds": body.max_rounds,
    })
    return {"status": "started", "scenario_id": scenario_id}

@router.post("/api/scenario/{scenario_id}/decide_v2")
async def submit_decision_v2(scenario_id: str, body: DecisionRequest):
    """사용자 결정을 Simulation Service에 전달."""
    await emit_command("sim_commands", {
        "type": "user_decision",
        "scenario_id": scenario_id,
        "decision_point_id": body.decision_point_id,
        "chosen_action": body.chosen_action,
    })
    return {"status": "decision_submitted"}
```

2. `backend/app/main.py`에 `simulation_v2` 라우터 등록 (기존 라우터와 공존).

3. 기존 `simulation_run.py`, `simulation_live.py` 라우터는 그대로 유지 — Phase 3에서 제거.

### 결과물

| 파일 | 상태 |
|---|---|
| `backend/app/routers/simulation_v2.py` | 신규 |
| `backend/app/main.py` | 수정 (라우터 추가) |

### 성공 기준

- `POST /api/scenario/{id}/start_v2` → Simulation Service가 LangGraph 실행 → Gateway SSE에서 이벤트 수신
- 기존 `/api/scenario/{id}/run` (MiroFish 경로) 정상 동작 유지

---

## 전체 Phase 1 완료 기준

- [ ] Simulation Service가 독립 서비스로 기동 (docker compose)
- [ ] LangGraph StateGraph가 stub 노드로 3라운드 실행 완료
- [ ] 각 노드 완료 시 PostgreSQL NOTIFY → Gateway SSE로 이벤트 전달
- [ ] Gateway에서 sim_commands로 시뮬레이션 시작/중지 제어 가능
- [ ] LangGraph 체크포인트가 PostgreSQL에 저장되어 서비스 재시작 후 복원 가능
- [ ] 기존 MiroFish 경로 정상 동작 유지 (dual-run)
