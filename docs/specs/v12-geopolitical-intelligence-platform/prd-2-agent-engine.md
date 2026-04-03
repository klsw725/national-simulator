# PRD-2: 지정학 에이전트 엔진

> Phase: 2 / 4
> 예상 기간: 3주
> 선행 조건: PRD-1 완료 (Simulation Service 골격, LangGraph StateGraph, NOTIFY/LISTEN)
> 참조: v12-spec.md §4 (온톨로지), §5.3 (에이전트 행동 모델)

---

## 목표

OASIS를 대체하는 **LLM 기반 지정학 에이전트 엔진**을 구현한다. 국가 행위자가 외교/경제/군사 행동을 직접 선택하고, DecisionEngine이 수치적 결과를 계산하며, 사용자가 워게임 방식으로 개입할 수 있다.

**이 Phase가 끝나면**: 전체 워게임 루프 동작. 시나리오 생성 → OSINT 기반 상황 분석 → 에이전트 행동 → 결정 포인트 개입 → 보고서 생성.

---

## M1: 상황 분석 노드 (analyze_situation)

### 배경

현재 `seed_generator.py`가 ShadowBroker OSINT 데이터 + 뉴스를 수집하여 시드 문서를 생성한다. 이 로직을 재사용하되, 출력을 지정학 시뮬레이션에 맞게 변환.

### 작업

1. `simulation-service/app/graph/nodes/analyze.py` 구현:
   - ShadowBroker 클라이언트로 OSINT 데이터 수집 (ships, flights, gdelt, news)
   - LLM 호출: OSINT 데이터 → 현재 지역 정세 요약 생성
   - 출력: `situation_summary` (1000-2000자 한국어 정세 요약)
   - 부수 출력: 주요 행위자 목록 (다음 노드 입력용)

2. 프롬프트:
   ```
   다음 OSINT 데이터를 분석하여 현재 지역 정세를 요약하십시오.
   - 주요 군사 자산 배치 현황
   - 최근 외교/군사/경제 이벤트
   - 긴장 요인과 완화 요인
   - 관련된 주요 국가/행위자 목록
   ```

3. OSINT 데이터 수집: `backend/app/clients/shadowbroker.py` 재사용. Simulation Service에서 ShadowBroker HTTP API 직접 호출.

### 결과물

| 파일 | 상태 |
|---|---|
| `simulation-service/app/graph/nodes/analyze.py` | 구현 (stub 대체) |

### 성공 기준

- ShadowBroker 데이터 수집 → LLM 요약 생성 → `situation_summary` 설정
- NOTIFY로 `phase_change(analyzing, 100)` 발행

---

## M2: 관계 구축 노드 (build_relations)

### 작업

1. `simulation-service/app/graph/nodes/relations.py` 구현:
   - LLM 호출: `situation_summary` + OSINT 데이터 → 엔티티 추출 + 관계 추출
   - 추출된 엔티티를 PRD-0의 온톨로지 유형으로 분류
   - DozerDB에 엔티티/관계 저장
   - `ontology_edge_history` 테이블에 관계 이력 기록

2. 엔티티 추출 프롬프트:
   ```
   다음 정세 요약에서 지정학 엔티티와 관계를 추출하십시오.
   엔티티 유형: NationState, MilitaryForce, Facility, StrategicRegion, ...
   관계 유형: ALLIED_WITH, HOSTILE_TO, DEPLOYED_TO, SANCTIONS_AGAINST, ...
   각 관계에 강도(0.0-1.0)를 부여하십시오.
   ```

3. DozerDB 연동: 기존 `external/mirofish-backend`의 graph builder 패턴 참조하되, OASIS 관련 로직은 제거.

### 결과물

| 파일 | 상태 |
|---|---|
| `simulation-service/app/graph/nodes/relations.py` | 구현 |
| `simulation-service/app/services/graph_manager.py` | 신규 (DozerDB CRUD) |

### 성공 기준

- LLM이 5+ 엔티티와 10+ 관계를 추출
- DozerDB에 그래프 저장 확인
- `ontology_edge_history`에 관계 이력 기록

---

## M3: 행위자 프로필 생성 노드 (create_actors)

### 작업

1. `simulation-service/app/graph/nodes/actors.py` 구현:
   - `situation_summary` + 추출된 엔티티 → 국가별 에이전트 프로필 생성
   - 각 프로필: 국가명, 군사력, 경제력, 이념, 동맹, 핵심 이익, 행동 성향
   - LLM 호출로 생성하되, OSINT 데이터로 뒷받침

2. 프로필 스키마:

```python
class ActorProfile(TypedDict):
    nation_code: str            # "US", "CN", "KR", ...
    country_name: str
    military_power: str         # "superpower" / "major" / "regional" / "minor"
    economic_power: str
    ideology: str               # 체제/이념 요약
    alliances: list[str]        # 동맹국 코드 목록
    core_interests: list[str]   # 핵심 이익 목록
    behavior_tendency: str      # 행동 성향 요약 (공격적/방어적/중재적/...)
    recent_actions: list[str]   # 최근 행동 이력
```

3. DecisionEngine 초기화: 각 행위자에 대해 `GeopoliticalActorState` 생성. 기존 `backend/app/geopolitics/models.py` 재사용.

### 결과물

| 파일 | 상태 |
|---|---|
| `simulation-service/app/graph/nodes/actors.py` | 구현 |
| `simulation-service/app/models/actor.py` | 신규 (ActorProfile 스키마) |

### 성공 기준

- 3-10개 국가 프로필 생성
- 각 프로필에 대해 GeopoliticalActorState 초기화
- NOTIFY `phase_change(configuring, 100)` 발행

---

## M4: 시뮬레이션 라운드 노드 (run_round)

### 배경

핵심 노드. 각 국가 에이전트가 LLM 호출로 행동을 결정한다. LangGraph의 `Send` API로 병렬 호출.

### 작업

1. `simulation-service/app/graph/nodes/round.py` 구현:

```python
async def run_round_node(state: SimulationState) -> dict:
    """각 에이전트에게 행동 결정을 요청하고 결과를 수집."""
    round_actions = []

    # 병렬로 에이전트 호출
    tasks = [
        call_agent(actor_code, state)
        for actor_code in state["actors"]
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, Exception):
            logger.error(f"Agent error: {result}")
            continue
        round_actions.extend(result)

    return {"round_actions": round_actions}
```

2. 에이전트 LLM 호출 (`call_agent`):
   - 시스템 프롬프트: v12-spec §5.3의 `ACTOR_SYSTEM_PROMPT` 적용
   - 컨텍스트: situation_summary, recent_osint, other_actors_recent_actions, tension_levels
   - 출력: 구조화된 행동 1-3개 (action_type, target, intensity, reasoning)
   - ⚠️ OpenAI Compatible API 가정. structured output (JSON mode) 사용하되 프로바이더 고유 기능 의존 금지.

3. 행동 출력 스키마:

```python
class AgentAction(TypedDict):
    actor: str                  # 행위자 코드
    action_type: str            # DIPLOMATIC_ACTIONS / ECONOMIC_ACTIONS / ... 중 선택
    target: str                 # 대상 국가/지역
    intensity: str              # "low" / "medium" / "high"
    reasoning: str              # 행동 근거 (한국어)
```

4. 행동 유형 정의 (`simulation-service/app/models/actions.py`):
   - v12-spec §5.3의 전체 행동 유형 목록 (외교 7종, 경제 5종, 군사 7종, 정보 4종, 메타 2종)
   - 각 행동의 기본 효과 (긴장도 변화, 자원 소모) 정의

5. 각 에이전트 행동마다 NOTIFY `agent_action` 이벤트 발행 (실시간 스트리밍).

### 결과물

| 파일 | 상태 |
|---|---|
| `simulation-service/app/graph/nodes/round.py` | 구현 |
| `simulation-service/app/models/actions.py` | 신규 |
| `simulation-service/app/services/agent_caller.py` | 신규 (LLM 호출 로직) |
| `simulation-service/app/prompts/actor_system.py` | 신규 (프롬프트 템플릿) |

### 성공 기준

- 5개 국가 에이전트가 병렬로 행동 결정 (< 15초)
- 각 행동이 유효한 action_type/target/intensity
- 실시간 `agent_action` NOTIFY 이벤트 발행

---

## M5: 결과 계산 노드 (calculate_results)

### 배경

기존 `DecisionEngine` (`backend/app/geopolitics/engine.py`)을 재사용한다. 에이전트의 행동을 수치적 결과(긴장도, 자원, 위협 인식)로 변환.

### 작업

1. `simulation-service/app/graph/nodes/results.py` 구현:
   - `DecisionEngine.from_state(state["decision_engine_state"])` 로 엔진 복원
   - 각 에이전트 행동에 대해 `engine.apply_action()` 호출
   - 신규 행동 유형(deploy_forces, impose_sanction 등)에 대한 효과 매핑 추가
   - `engine.run_single_round()` 호출
   - 업데이트된 상태 직렬화

2. DecisionEngine 확장 (필요 시):
   - 기존 엔진의 `apply_action` 인터페이스를 유지하면서 새 행동 유형을 처리하는 어댑터 생성
   - `simulation-service/app/services/engine_adapter.py` — 에이전트 행동 → DecisionEngine 입력 변환

3. ⚠️ `DecisionEngine`은 `backend/app/geopolitics/`에 위치. Simulation Service에서 사용하려면:
   - 옵션 A: 공유 라이브러리로 추출 (shared/ 디렉토리)
   - 옵션 B: Simulation Service에 코드 복사 (당분간)
   - **권장: 옵션 A** — `shared/geopolitics/` 에 엔진 코드를 이동하고 양쪽에서 임포트

### 결과물

| 파일 | 상태 |
|---|---|
| `simulation-service/app/graph/nodes/results.py` | 구현 |
| `simulation-service/app/services/engine_adapter.py` | 신규 |
| `shared/geopolitics/` | 신규 (기존 backend/app/geopolitics에서 이동) |

### 성공 기준

- 에이전트 행동이 긴장도, 자원, 위협 인식 수치에 반영
- `decision_engine_state` 직렬화/역직렬화 정상 동작
- 기존 DecisionEngine 테스트 (있다면) 통과

---

## M6: 워게임 개입 노드 (check_intervention + apply_decision)

### 배경

기존 `should_pause()` 로직과 `build_actor_response_options()` 을 재사용하여 LangGraph `interrupt()`와 연결.

### 작업

1. `simulation-service/app/graph/nodes/intervene.py` 구현:

```python
async def check_intervention_node(state: SimulationState) -> dict:
    """워게임 개입 판정. should_pause 재사용."""

    engine = DecisionEngine.from_state(state["decision_engine_state"])

    if state["current_round"] >= state["max_rounds"]:
        return {"status": "complete"}

    # should_pause 로직 재사용
    should_stop = should_pause(
        engine_state=engine,
        round_num=state["current_round"],
        tension_levels=state["tension_levels"],
    )

    if should_stop:
        # 결정 옵션 생성 (기존 build_actor_response_options 재사용)
        options = build_actor_response_options(engine)
        decision_point = {
            "id": f"dp_{uuid4().hex[:12]}",
            "round": state["current_round"],
            "trigger": should_stop.reason,
            "options": options,
        }

        # NOTIFY로 프론트엔드에 개입 요청 전송
        await emitter.emit_intervention_required(state["scenario_id"], decision_point)

        # LangGraph interrupt — 사용자 결정을 기다림
        return interrupt({"decision_point": decision_point})

    return {"decision_point": None}
```

2. `simulation-service/app/graph/nodes/decision.py` 구현:

```python
async def apply_decision_node(state: SimulationState) -> dict:
    """사용자 결정 반영. override_next_action 재사용."""

    user_decision = state["user_decision"]
    engine = DecisionEngine.from_state(state["decision_engine_state"])

    # 기존 override_next_action / apply_direction_deltas 재사용
    engine.override_next_action(
        actor=user_decision["actor"],
        action=user_decision["chosen_action"],
    )

    return {
        "decision_engine_state": engine.serialize_state(),
        "user_decision": None,
        "decision_point": None,
    }
```

3. resume 로직: Gateway의 `decide_v2` 라우터에서 `user_decision` 명령 → Simulation Service가 `graph.aupdate_state(config, {"user_decision": ...})` + `graph.ainvoke(None, config)` 로 resume.

### 결과물

| 파일 | 상태 |
|---|---|
| `simulation-service/app/graph/nodes/intervene.py` | 구현 |
| `simulation-service/app/graph/nodes/decision.py` | 구현 |

### 성공 기준

- 긴장도 임계치 초과 시 interrupt 발생
- NOTIFY `intervention_required` 이벤트 → Gateway SSE → 프론트엔드
- 사용자 결정 전송 → resume → 다음 라운드 실행 (결정 반영됨)

---

## M7: OSINT 실시간 주입

### 작업

1. 매 라운드 시작 전 ShadowBroker에서 최신 OSINT 데이터를 조회하여 에이전트 컨텍스트에 주입:
   - 신규 군사 자산 배치 (ships, flights)
   - GDELT 신규 이벤트
   - GPS 재밍 활동
   - 기타 실시간 변화

2. `simulation-service/app/services/osint_injector.py` 신규 생성:

```python
async def get_latest_osint(shadowbroker_url: str, region: dict) -> dict:
    """ShadowBroker에서 최신 OSINT 데이터 조회 및 온톨로지 매핑."""
    # PRD-0의 mapping_rules.py 사용
```

3. `run_round` 노드에서 호출: 에이전트 프롬프트의 `{recent_osint_observations}` 섹션에 주입.

### 결과물

| 파일 | 상태 |
|---|---|
| `simulation-service/app/services/osint_injector.py` | 신규 |
| `simulation-service/app/graph/nodes/round.py` | 수정 |

### 성공 기준

- 라운드별 OSINT 데이터가 에이전트 프롬프트에 포함
- 신규 군사 배치가 에이전트 행동에 영향 (예: 함대 배치 → 대응 행동)

---

## M8: 보고서 생성 노드 (generate_report)

### 작업

1. `simulation-service/app/graph/nodes/report.py` 구현:
   - 전체 시뮬레이션 이력 (action_history) → LLM → 인텔리전스 브리핑
   - 기존 `backend/app/services/report_agent.py` 프롬프트 스타일 참조 (인텔리전스 보고서 형식)

2. 보고서 구조:
   - 상황 요약 (Executive Summary)
   - 라운드별 주요 이벤트 타임라인
   - 행위자별 행동 분석
   - 긴장도 추이 분석
   - 예측 시나리오 (가능한 향후 전개)
   - 핵심 불확실성 요소

3. 보고서를 PostgreSQL에 저장하고 NOTIFY `report_ready` 발행.

### 결과물

| 파일 | 상태 |
|---|---|
| `simulation-service/app/graph/nodes/report.py` | 구현 |
| `simulation-service/app/prompts/report_system.py` | 신규 |

### 성공 기준

- 시뮬레이션 완료 후 인텔리전스 브리핑 형식의 보고서 생성
- 보고서에 라운드별 타임라인, 행위자 분석, 예측 포함
- NOTIFY `report_ready` → Gateway SSE → 프론트엔드

---

## 전체 Phase 2 완료 기준

- [ ] OSINT 데이터가 온톨로지를 통해 시뮬레이션 컨텍스트로 자동 변환
- [ ] 국가 에이전트가 외교/경제/군사 행동을 직접 선택 (소셜미디어 매핑 없음)
- [ ] DecisionEngine이 행동을 수치적 결과로 변환 (긴장도, 자원)
- [ ] 워게임 interrupt/resume 동작 (사용자 결정이 다음 라운드에 반영)
- [ ] 매 라운드 OSINT 데이터가 실시간으로 에이전트 컨텍스트에 주입
- [ ] 인텔리전스 브리핑 스타일 보고서 자동 생성
- [ ] 라운드 실행 시간: < 30초 (에이전트 5개 병렬)
- [ ] 전체 E2E: 시나리오 생성 → 시뮬레이션 → 개입 → 보고서 → SSE로 실시간 확인
