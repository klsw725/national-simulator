# PRD: 워게임 루프 — 라운드 단위 외교 시뮬레이션

> Status: Draft
> Created: 2026-03-31
> Dependencies: v9-interactive-geopolitics (DecisionEngine, should_pause, snapshots), v4-interactive-simulation (DecisionPoint, checkpoint), v7-whatif-counterfactual (WhatIfEngine, MAXS 메트릭)
> 관련 스펙: V5-SPEC.md (지정학 엔진), V4-SPEC.md (DecisionPoint)
> 버전: v11.0

---

## 1. 문제 정의

현재 시스템은 **직선형 파이프라인**이다: MiroFish 시뮬레이션이 전체 라운드를 통째로 실행하고, 완료 후에야 지정학 엔진이 동작한다. v9에서 추가한 인터랙티브 지정학(ACTOR_ROLE, GAME_MASTER)도 시뮬레이션 완료 후의 사후 분석 단계에서만 작동한다. 에이전트는 지정학적 이벤트에 반응하지 않고, 사용자의 전략적 결정이 에이전트 행동에 영향을 미치지 않는다.

이 프로젝트의 본질은 **외교 시뮬레이션**이다. 사용자가 국가안보보좌관 역할로 라운드별로 상황을 관찰하고, 전략적 결정을 내리고, 그 결정이 다음 라운드의 에이전트 행동과 지정학적 역학에 실질적으로 영향을 미치는 워게임 루프가 필요하다.

### 현황

| 역량 | 현재 상태 | 필요 |
|------|----------|------|
| MiroFish 시뮬레이션 | 전체 라운드 일괄 실행 (중간 개입 불가) | 라운드 단위 실행 + 라운드 간 개입 |
| 지정학 엔진 | 시뮬레이션 완료 후 사후 분석 | 매 라운드 종료 후 실시간 실행 |
| 에이전트 ↔ 지정학 연동 | 단방향: 에이전트 액션 → 지정학 이벤트 | 양방향: 에이전트 ↔ 지정학 피드백 루프 |
| 사용자 결정 → 에이전트 반영 | ❌ 없음 | 결정이 시스템 포스트로 에이전트 컨텍스트에 주입 |
| UI 패러다임 | 탭 기반 대시보드 (결과 브라우징) | 페이즈 기반 상황실 (라이브 참여) |
| 실시간 통신 | 폴링 (5초 간격) | SSE 또는 WebSocket (페이즈 전환, 이벤트 알림) |
| Event Injection | DB 저장만 (미소비) | 시스템 포스트로 OASIS 환경에 실제 주입 |

### 기존 인프라 재활용

v9까지 구축한 다음 인프라는 **변경 없이 그대로 재활용**한다:

| 인프라 | 파일 | 재활용 방식 |
|--------|------|-----------|
| `DecisionEngine.run_single_round()` | `geopolitics/engine.py` | 매 라운드 후 호출 |
| `should_pause()` | `services/geopolitics_interactive.py` | 라운드별 pause 판정 |
| `build_actor_response_options()` | `services/geopolitics_interactive.py` | 결정 카드 옵션 생성 |
| `build_direction_options()` | `services/geopolitics_interactive.py` | 게임 마스터 옵션 생성 |
| `save_geopolitics_snapshot()` | `services/geopolitics_interactive.py` | 라운드별 상태 저장 |
| `DecisionEngine.serialize_state()` / `from_state()` | `geopolitics/engine.py` | pause/resume 상태 복원 |
| `override_next_action()` / `apply_direction_deltas()` | `geopolitics/engine.py` | 사용자 결정 반영 |
| Decision Points CRUD | `routers/decision_point.py` | 결정 생성/조회/해소 |
| `geopolitics_snapshots` 테이블 | `database.py` | 엔진 상태 영속화 |
| `geopolitics_events` 테이블 | `database.py` | 이벤트 저장 |
| `injected_events` 테이블 | `database.py` | 주입 이벤트 저장 |
| `WhatIfEngine` | `services/whatif_engine.py` | 특정 라운드에서 분기 |
| `GeopoliticsDecisionView.tsx` | `components/simulation/` | 결정 카드 UI |
| `LiveActionFeed.tsx` | `components/simulation/` | 소셜 미디어 피드 |
| `LiveStats.tsx` | `components/simulation/` | 라운드 진행 표시 |

### 제약 조건

- **OASIS `env.step()` 은 atomic**: 라운드 내부에서는 중단 불가. v11은 라운드 사이 개입만 지원한다. 라운드 내부 개입은 향후 `env.step()` 분할 시 v12에서 다룬다.
- **에이전트 메모리는 in-process**: OASIS 에이전트의 대화 기록, 신념 상태가 프로세스 메모리에만 존재. 프로세스 종료 시 손실. Zep 그래프 메모리(`enable_graph_memory_update`) 플래그는 존재하나 아직 검증되지 않음.
- **LLM은 OpenAI Compatible API**: 특정 프로바이더 고유 기능에 의존하지 않는다.
- **기존 auto 모드 완전 호환**: `geopolitics_mode: "auto"` + `wargame_enabled: false` 시 현재 동작(직선형 파이프라인)과 100% 동일해야 한다.
- **MiroFish는 subprocess**: `run_parallel_simulation.py`가 별도 프로세스로 실행. IPC는 stdin/stdout으로 한다.

---

## 2. 솔루션 개요

### 워게임 루프

```
┌─────────────────────────────────────────────────────────────────┐
│  Phase 0: 파이프라인 (기존 유지)                                  │
│  Seed → Ontology → Graph → Profiles → Config                   │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│  Phase 1: MiroFish 시작 (round_control_enabled=true)            │
│  환경 초기화 → 에이전트 로드 → ready 신호                        │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│  Phase 2: 라운드 루프                                            │
│                                                                 │
│  오케스트레이터 → proceed 신호 (+ inject_context)                 │
│  MiroFish 라운드 실행 (env.step, atomic)                         │
│  MiroFish → round_complete 신호 (+ actions)                     │
│                                                                 │
│  오케스트레이터:                                                  │
│    1. 액션 DB 저장                                               │
│    2. 지정학 엔진 run_single_round(actions)                      │
│    3. should_pause() 판정                                        │
│       - No → 컨텍스트 준비 → proceed                             │
│       - Yes → 브리핑 생성 → Decision Point → 사용자 대기          │
│               결정 수신 → 엔진 상태 반영 → 컨텍스트 준비 → proceed │
│                                                                 │
│  MiroFish: inject_context → 시스템 포스트 생성 → 다음 라운드       │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│  Phase 3: 완료                                                   │
│  stop 신호 → 환경 정리 → 최종 리포트 → 디브리프                   │
└─────────────────────────────────────────────────────────────────┘
```

### 프론트엔드: 탭 → 상황실

기존 탭 기반 `SimulationPanel`을 **페이즈 기반 상황실 UI**로 전환한다. 핵심 변경:

- 상단: 탭 바 → **페이즈 인디케이터** (시뮬레이션 → 브리핑 → 결정 → 확정)
- 중앙: 맵은 항상 표시. 페이즈에 따라 **오버레이가 전환**
- 좌측: 탭 목록 → **렌즈 선택** (정보전 / 외교 / 군사 / 경제)
- 우측: 고정 탭 콘텐츠 → **컨텍스트 패널** (선택된 객체 상세 + 액션)
- 하단: 없음 → **피드 + 타임라인 바**
- 결정: 별도 탭 → **페이즈 전환 시 자동 오버레이**

### 핵심 설계 결정

| 결정 | 선택 | 근거 |
|------|------|------|
| 라운드 제어 방식 | stdin/stdout IPC (NDJSON) | 기존 subprocess 모델 + interview IPC 패턴 재활용. 새 제어 플레인 불필요 |
| 컨텍스트 주입 방식 | OASIS 환경에 시스템 포스트 | 에이전트가 기존 인식 루프(피드 읽기)로 자연스럽게 소화. 프롬프트 수정 불필요 |
| 기계적 제약 | 환경 상태 직접 변경 | 제재로 특정 행동 차단 등 하드 제약은 포스트가 아닌 환경 규칙으로 |
| 피드백 방향 | 양방향 비대칭 | 소셜→지정학 (기존 매핑), 지정학→소셜 (시스템 포스트). 출처 태깅으로 폭주 방지 |
| 동기/비동기 | 동기 배리어 (라운드 단위) | 인과성 보존. 다음 라운드는 지정학 + 사용자 결정이 확정된 후에만 시작 |
| 프로세스 수명 | 일시정지 시 프로세스 유지 (TTL 30분) | 에이전트 메모리가 in-process. 종료 시 맥락 손실 |
| TTL 초과 | 깨끗하게 종료 → 마지막 완료 라운드부터 재개 | 에이전트 맥락 손실되나 시뮬레이션 연속성 유지 |
| UI 패러다임 | 페이즈 기반 상황실 | 전문 워게임 패턴 (Battleplan, XCOM, Paradox). 관찰/행동 하드 분리 |
| 결정 표시 | 페이즈 전환 시 자동 오버레이 | 탭 이동 불필요. 결정 시점에 자동으로 나타남 |
| 맵 렌즈 | Victoria 3 스타일 컨텍스트 동기화 | 활성 렌즈에 따라 맵 오버레이 자동 전환 |
| stdout 분리 | stderr=로그, stdout=제어 메시지 | 프로토콜 오염 방지. Oracle 지적 사항 |
| 피드백 폭주 방지 | 출처 태깅 + 라운드당 디바운스 | 지정학 이벤트→시스템 포스트→에이전트 반응→같은 이벤트 재생성 무한루프 차단 |

---

## 3. 기술 상세

### 3.1 IPC Round Control Protocol

MiroFish `run_parallel_simulation.py`에 라운드 배리어를 추가한다. 프로토콜은 NDJSON (줄 단위 JSON, stdout 전용). 로그는 stderr로 분리.

**메시지 타입:**

| 방향 | type | 필드 | 설명 |
|------|------|------|------|
| MF→Orch | `ready` | `run_id`, `total_rounds`, `platforms` | 환경 초기화 완료 |
| Orch→MF | `proceed` | `round`, `inject_context?` | 다음 라운드 실행 허가 + 선택적 컨텍스트 주입 |
| MF→Orch | `round_complete` | `round`, `actions[]`, `stats` | 라운드 완료 + 에이전트 액션 |
| Orch→MF | `stop` | `reason` | 시뮬레이션 종료 |
| MF→Orch | `error` | `round`, `message`, `recoverable` | 에러 보고 |
| Orch→MF | `heartbeat` | `timestamp` | 프로세스 생존 확인 (30초 간격) |
| MF→Orch | `heartbeat_ack` | `timestamp` | 하트비트 응답 |

**`inject_context` 구조:**

```python
{
    "system_posts": [
        {
            "platform": "twitter",          # "twitter" | "reddit"
            "author": "@BreakingNews",      # 시스템 계정
            "content": "중국 해군, 남중국해서 대규모 군사훈련 실시 예정. 주변국 우려 확산.",
            "metadata": {
                "source": "geo_event",      # 출처 태깅 (피드백 폭주 방지용)
                "event_type": "military_exercise",
                "event_id": "ge_abc123",
                "round": 3,
            }
        }
    ],
    "env_constraints": [                     # 선택적: 기계적 제약
        {
            "type": "block_action",
            "target_agents": ["agent_CN_1"],
            "blocked_actions": ["create_post"],  # 제재로 발언 차단 등
            "reason": "UN 제재 결의안 2840호",
            "duration_rounds": 2,
        }
    ]
}
```

**`run_parallel_simulation.py` 수정:**

```python
# 기존 루프에 라운드 배리어 추가

async def run_simulation_loop(..., round_control_enabled: bool = False):
    if round_control_enabled:
        # 초기화 완료 신호
        _send_control({"type": "ready", "run_id": run_id, "total_rounds": total_rounds,
                        "platforms": ["twitter", "reddit"]})

    for round_num in range(total_rounds):
        if _shutdown_event and _shutdown_event.is_set():
            break

        # 라운드 배리어: 오케스트레이터 신호 대기
        if round_control_enabled:
            signal = await _wait_for_control_signal()
            if signal["type"] == "stop":
                break
            if signal["type"] == "proceed":
                if "inject_context" in signal:
                    await _inject_context_to_env(result.env, signal["inject_context"])

        # 기존 라운드 실행 (atomic)
        active_agents = get_active_agents_for_round(result.env, config, simulated_hour, round_num)
        action_logger.log_round_start(round_num + 1, simulated_hour)
        actions = {agent: LLMAction() for _, agent in active_agents}
        await result.env.step(actions)
        actual_actions, last_rowid = fetch_new_actions_from_db(db_path, last_rowid, agent_names)
        action_logger.log_round_end(round_num + 1, round_action_count)

        # 라운드 완료 신호
        if round_control_enabled:
            _send_control({"type": "round_complete", "round": round_num + 1,
                            "actions": actual_actions, "stats": {...}})

def _send_control(msg: dict):
    """stdout으로 NDJSON 제어 메시지 전송. 로그는 stderr."""
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()

async def _wait_for_control_signal() -> dict:
    """stdin에서 NDJSON 제어 메시지 대기."""
    line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
    return json.loads(line.strip())

async def _inject_context_to_env(env, context: dict):
    """시스템 포스트를 OASIS 환경에 주입."""
    for post in context.get("system_posts", []):
        # OASIS 환경의 해당 플랫폼에 시스템 포스트 생성
        await env.create_system_post(
            platform=post["platform"],
            author=post["author"],
            content=post["content"],
            metadata=post.get("metadata", {}),
        )
    for constraint in context.get("env_constraints", []):
        await env.apply_constraint(constraint)
```

**`round_control_enabled` 활성화 조건:**

`simulation_config.json`에 `"round_control_enabled": true` 추가. 오케스트레이터가 `wargame_enabled=True`일 때만 설정. `false`면 기존 동작(연속 실행) 그대로.

### 3.2 Orchestrator Wargame Coordinator

`SimulationOrchestrator`에 워게임 루프 메서드 추가. 기존 `run_pipeline()`은 그대로 유지하고, `run_wargame_pipeline()`을 신규 추가한다.

```python
# backend/app/services/simulation_orchestrator.py

async def run_wargame_pipeline(
    self,
    scenario_id: str,
    result_id: str,
    seed_text: str,
    max_rounds: int,
    simulation_params: SimulationParams,
) -> None:
    """워게임 루프: 라운드 단위 시뮬레이션 + 지정학 + 사용자 결정."""

    # Phase 0: 기존 파이프라인 (ontology → graph → profiles → config)
    ontology_result = await self._step_ontology(...)
    project_id = ontology_result.get("project_id", "")
    await self._step_graph_build(scenario_id, result_id, project_id)
    mf_simulation_id = await self._step_create_prepare(...)

    # Phase 1: MiroFish 시작 (round_control_enabled=true)
    process = await self._start_mirofish_with_round_control(
        mf_simulation_id, max_rounds, simulation_params
    )
    ready_signal = await self._read_control_signal(process)
    assert ready_signal["type"] == "ready"

    # 지정학 엔진 초기화 (빈 상태 — 첫 라운드 액션 수집 후 actor 생성)
    engine = None
    all_actions = []

    # Phase 2: 라운드 루프
    for round_num in range(1, max_rounds + 1):
        # 2a. 컨텍스트 준비 (2라운드 이상부터)
        inject_context = None
        if engine and round_num > 1:
            inject_context = self._build_inject_context(engine, round_num)

        # 2b. proceed 신호 전송
        await self._send_control_signal(process, {
            "type": "proceed",
            "round": round_num,
            **({"inject_context": inject_context} if inject_context else {}),
        })

        # 2c. 라운드 완료 대기
        signal = await self._read_control_signal(process)
        if signal["type"] == "error":
            await self._handle_round_error(scenario_id, result_id, signal)
            break
        assert signal["type"] == "round_complete"

        round_actions = signal["actions"]
        all_actions.extend(round_actions)

        # 2d. 액션 DB 저장
        await self._save_round_actions(result_id, round_num, round_actions)

        # 2e. 지정학 엔진 실행
        if engine is None and round_num >= 1:
            engine = self._init_geopolitics_engine(all_actions)

        geo_round_actions = self._map_round_actions_to_geopolitics(
            round_actions, source_tag="simulation"
        )
        engine.feed_round_actions(geo_round_actions)
        round_result = engine.run_single_round()

        # 2f. 지정학 이벤트 DB 저장
        await self._save_geopolitics_events(scenario_id, result_id, round_result)

        # 2g. 프론트엔드 업데이트 (SSE)
        await self._emit_round_update(scenario_id, result_id, round_num, round_result)

        # 2h. should_pause() 판정
        if should_pause(round_result, simulation_params.geopolitics_mode,
                        simulation_params.geopolitics_player_actor_id,
                        simulation_params.geopolitics_pause_threshold):

            # 스냅샷 저장
            snapshot_id = await save_geopolitics_snapshot(
                scenario_id, result_id, round_num, engine,
                simulation_params.geopolitics_mode,
                simulation_params.geopolitics_player_actor_id,
            )

            # 브리핑 생성
            briefing = self._generate_round_briefing(round_num, round_result, engine)

            # Decision Point 생성 (기존 로직 재활용)
            if simulation_params.geopolitics_mode == GeopoliticsMode.ACTOR_ROLE:
                trigger_event = self._find_trigger_event(
                    round_result, simulation_params.geopolitics_player_actor_id
                )
                options = build_actor_response_options(
                    engine, simulation_params.geopolitics_player_actor_id, trigger_event
                )
                dp_type = "geopolitics_actor_response"
            else:
                options = build_direction_options(round_result)
                dp_type = "geopolitics_direction"

            dp_id = await self._create_decision_point(scenario_id, dp_type, options, ...)

            # 상태 업데이트 + 프론트엔드 알림
            await self._update_status(
                scenario_id, result_id,
                f"wargame:paused:round_{round_num}",
            )
            await self._emit_decision_required(scenario_id, result_id, dp_id, briefing)

            # 사용자 결정 대기 (비동기 — resume 엔드포인트에서 처리)
            # 하트비트 루프 시작
            await self._start_heartbeat_loop(process, ttl_minutes=30)
            return  # resume 시 _continue_wargame()에서 이어감

    # Phase 3: 완료
    await self._send_control_signal(process, {"type": "stop", "reason": "completed"})
    await self._step_report(...)
    await self._finalize_wargame(scenario_id, result_id, engine)
```

**재개 로직** (`_continue_wargame`):

```python
async def _continue_wargame(
    self, scenario_id: str, result_id: str, process, simulation_params: SimulationParams,
) -> None:
    """워게임 일시정지에서 재개. 기존 v9 _continue_geopolitics와 동일한 패턴."""

    # 1. 스냅샷 + Decision Point 복원 (기존 로직)
    snapshot = await _get_latest_geopolitics_snapshot(scenario_id, result_id)
    engine = DecisionEngine.from_state(json.loads(snapshot["engine_state"]))
    dp = await _get_resolved_decision_point(snapshot["pending_decision_point_id"])

    # 2. 사용자 결정 반영 (기존 로직)
    if simulation_params.geopolitics_mode == GeopoliticsMode.ACTOR_ROLE:
        engine.override_next_action(
            simulation_params.geopolitics_player_actor_id, dp.selected_option_id
        )
    elif simulation_params.geopolitics_mode == GeopoliticsMode.GAME_MASTER:
        selected = next(o for o in dp.options if o["id"] == dp.selected_option_id)
        engine.apply_direction_deltas(
            selected["data"]["state_deltas"], selected["data"]["applies_to"]
        )

    # 3. 나머지 라운드 루프 재개 (위 run_wargame_pipeline Phase 2와 동일)
    remaining_start = snapshot["round_number"] + 1
    # ... 동일한 라운드 루프 ...
```

### 3.3 컨텍스트 주입 엔진

지정학 이벤트 + 사용자 결정을 에이전트가 인지할 수 있는 형태로 변환한다.

```python
# backend/app/services/context_injection.py (신규)

# 이벤트 타입 → 시스템 포스트 템플릿
EVENT_POST_TEMPLATES = {
    "military_movement": {
        "author": "@DefenseIntel",
        "template": "{source_actor} 군이 {target_region} 방면으로 병력 이동을 개시했습니다. 군사 전문가들은 이를 {assessment}으로 분석하고 있습니다.",
    },
    "military_exercise": {
        "author": "@MilitaryWatch",
        "template": "{source_actor}이(가) {target_region}에서 대규모 군사훈련을 실시합니다. 훈련 규모: {magnitude_desc}.",
    },
    "sanction_impose": {
        "author": "@EconAlert",
        "template": "속보: {source_actor}이(가) {target_actor}에 대한 경제 제재를 발동했습니다. 대상: {sanction_detail}.",
    },
    "trade_restriction": {
        "author": "@TradeMonitor",
        "template": "{source_actor}이(가) {target_actor}에 대한 무역 제한 조치를 시행합니다. {restriction_detail}.",
    },
    "diplomatic_statement": {
        "author": "@DiplomaticBrief",
        "template": "{source_actor} 외교부 성명: \"{statement_content}\"",
    },
    "treaty_sign": {
        "author": "@TreatyWatch",
        "template": "{source_actor}와(과) {target_actor}이(가) {treaty_type} 협정에 서명했습니다.",
    },
}

MAGNITUDE_DESCRIPTIONS = {
    (0.0, 0.3): "소규모",
    (0.3, 0.6): "중규모",
    (0.6, 0.8): "대규모",
    (0.8, 1.0): "전례 없는 규모의",
}

# 사용자 결정 → 시스템 포스트
DECISION_POST_TEMPLATES = {
    "military_movement":   "{actor} 정부가 군사적 대응을 결정했습니다. 군 관계자에 따르면 병력 이동이 시작되었습니다.",
    "sanction_impose":     "{actor} 정부가 경제 제재 시행을 공식 발표했습니다.",
    "diplomatic_statement": "{actor} 외교부가 공식 성명을 발표하여 외교적 해결을 촉구했습니다.",
    "treaty_sign":         "{actor} 정부가 동맹 강화를 위한 새로운 협정 체결을 추진합니다.",
    "do_nothing":          None,  # 관망 시 포스트 없음
}


def build_inject_context(
    engine: DecisionEngine,
    round_result: dict,
    user_decision: dict | None = None,
) -> dict:
    """지정학 라운드 결과 + 사용자 결정 → inject_context 구조 생성."""
    system_posts = []

    # 1. 지정학 이벤트 → 시스템 포스트
    for event in round_result.get("events", []) + round_result.get("cascade_events", []):
        template_info = EVENT_POST_TEMPLATES.get(event["event_type"])
        if not template_info:
            continue
        content = _render_event_post(template_info["template"], event, engine)
        system_posts.append({
            "platform": "twitter",
            "author": template_info["author"],
            "content": content,
            "metadata": {
                "source": "geo_event",
                "event_type": event["event_type"],
                "event_id": event.get("id", ""),
                "round": engine.current_round,
            },
        })

    # 2. 사용자 결정 → 시스템 포스트
    if user_decision:
        action = user_decision.get("action")
        actor_name = user_decision.get("actor_name", "해당 국가")
        template = DECISION_POST_TEMPLATES.get(action)
        if template:
            system_posts.append({
                "platform": "twitter",
                "author": "@OfficialStatement",
                "content": template.format(actor=actor_name),
                "metadata": {
                    "source": "user_decision",
                    "action": action,
                    "round": engine.current_round,
                },
            })

    return {"system_posts": system_posts, "env_constraints": []}
```

### 3.4 피드백 폭주 방지

지정학 이벤트 → 시스템 포스트 → 에이전트 반응 → `map_actions_to_geopolitics` → 동일 이벤트 재생성 무한루프를 차단한다.

```python
# backend/app/services/geopolitics_mapper.py — 수정

def map_actions_to_geopolitics(
    actions: list[dict],
    source_filter: str | None = None,  # 신규: 출처 필터
) -> list[dict]:
    """MiroFish 액션 → 지정학 이벤트 타입 매핑. 출처 태깅된 액션은 감쇠/스킵."""
    geo_actions = []
    seen_event_types_this_round = set()  # 라운드당 디바운스

    for action in actions:
        metadata = action.get("metadata", {})

        # geo_event 출처 액션: 감쇠 또는 스킵
        if metadata.get("source") == "geo_event":
            continue  # v11: 시스템 포스트에 대한 반응은 지정학 매핑에서 제외

        # user_decision 출처 액션: 이미 엔진에 반영됨. 중복 방지.
        if metadata.get("source") == "user_decision":
            continue

        # 기존 매핑 로직
        event_type = _map_action_type(action["action_type"])
        if event_type and event_type not in seen_event_types_this_round:
            geo_actions.append({**action, "geopolitics_type": event_type})
            seen_event_types_this_round.add(event_type)

    return geo_actions
```

### 3.5 프로세스 수명 관리

```python
# backend/app/services/simulation_orchestrator.py

WARGAME_IDLE_TTL_MINUTES = 30
HEARTBEAT_INTERVAL_SECONDS = 30

async def _start_heartbeat_loop(self, process, ttl_minutes: int = 30):
    """일시정지 중 프로세스 생존 확인. TTL 초과 시 정리."""
    deadline = datetime.utcnow() + timedelta(minutes=ttl_minutes)

    while datetime.utcnow() < deadline:
        await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)

        # 프로세스 생존 확인
        if process.returncode is not None:
            # 프로세스 크래시 — 복구 마크
            await self._mark_process_crashed(...)
            return

        # 하트비트 전송
        await self._send_control_signal(process, {
            "type": "heartbeat", "timestamp": datetime.utcnow().isoformat()
        })

        # Decision Point 해소 여부 확인
        if await self._is_decision_resolved(...):
            return  # resume 트리거됨

    # TTL 초과: 프로세스 정리 + 자동 완료
    await self._send_control_signal(process, {"type": "stop", "reason": "idle_timeout"})
    await self._auto_complete_remaining_rounds(...)
```

**크래시 복구:**

매 라운드 완료 후 오케스트레이터 상태를 DB에 저장한다:

```python
# wargame_state 테이블 (신규)
CREATE TABLE IF NOT EXISTS wargame_state (
    id TEXT PRIMARY KEY,
    scenario_id TEXT NOT NULL REFERENCES scenarios(id),
    result_id TEXT NOT NULL,
    current_round INTEGER NOT NULL,
    total_rounds INTEGER NOT NULL,
    engine_state TEXT NOT NULL,           -- JSON
    process_pid INTEGER,
    status TEXT NOT NULL,                 -- running | paused | crashed | completed
    last_heartbeat TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

재시작 시 `wargame_state`에서 `current_round`를 확인하고, 해당 라운드부터 재개. 에이전트 맥락은 손실되나 시뮬레이션 연속성(지정학 상태, 이벤트 히스토리)은 유지.

### 3.6 SimulationParams 확장

```python
# backend/app/models/scenario.py

class SimulationParams(BaseModel):
    # 기존 필드
    geopolitics_enabled: bool = True
    geopolitics_mode: GeopoliticsMode = GeopoliticsMode.AUTO
    geopolitics_player_actor_id: str | None = None
    geopolitics_rounds: int = 3
    geopolitics_pause_threshold: float = 0.5

    # v11 신규 필드
    wargame_enabled: bool = False           # True면 워게임 루프, False면 기존 직선형
    wargame_idle_ttl_minutes: int = 30      # 일시정지 최대 대기 시간
```

`wargame_enabled=True`면 `run_wargame_pipeline()`, `False`면 기존 `run_pipeline()` 호출. 이로써 기존 동작과 100% 호환.

### 3.7 SSE (Server-Sent Events) 실시간 업데이트

기존 폴링을 SSE로 전환한다. 워게임 루프의 페이즈 전환, 라운드 완료, 결정 요청 등을 실시간으로 프론트엔드에 푸시.

```python
# backend/app/routers/simulation_events.py (신규)

from sse_starlette.sse import EventSourceResponse

@router.get("/api/scenario/{scenario_id}/events")
async def simulation_events(scenario_id: str):
    """SSE 스트림: 워게임 루프 실시간 이벤트."""
    async def event_generator():
        async for event in event_bus.subscribe(scenario_id):
            yield {
                "event": event["type"],      # round_complete, decision_required, phase_change, ...
                "data": json.dumps(event["data"]),
            }
    return EventSourceResponse(event_generator())
```

**이벤트 타입:**

| event | data | 트리거 시점 |
|-------|------|-----------|
| `phase_change` | `{phase, round}` | 시뮬레이션→브리핑→결정→확정 전환 |
| `round_complete` | `{round, actions_count, geo_events}` | 매 라운드 완료 |
| `decision_required` | `{decision_point_id, briefing}` | should_pause() 트리거 |
| `decision_resolved` | `{decision_point_id, selected}` | 사용자 결정 확정 |
| `round_stats` | `{round, tension, actor_states}` | 라운드별 상태 업데이트 |
| `simulation_complete` | `{total_rounds, final_state}` | 전체 시뮬레이션 완료 |
| `heartbeat` | `{timestamp}` | 30초 간격 |

### 3.8 프론트엔드: 페이즈 기반 상황실

#### 화면 레이아웃

```
┌───────────────────────────────────────────────────────────────────────┐
│ [● PHASE 1: 시뮬레이션] → [○ 브리핑] → [○ 결정] → [○ 확정]           │
│ Round 3/8          🇺🇸 USA (ACTOR_ROLE)          Tension: ■■■□□ 0.6  │
├───────────┬──────────────────────────────────┬───────────────────────┤
│           │                                  │                      │
│  렌즈     │         MAP (중앙, 항상 표시)       │   컨텍스트 패널       │
│  패널     │                                  │                      │
│           │   · OSINT 데이터 레이어            │   선택된 객체의       │
│  [정보전]  │   · 에이전트 활동 마커             │   상세정보            │
│  [외교]    │   · 지정학 이벤트 마커             │   + 가능한 액션       │
│  [군사]    │   · 긴장도 히트맵                  │                      │
│  [경제]    │                                  │   ─────────────       │
│           │   (활성 렌즈에 따라 오버레이 전환)   │   Actor 상태 요약     │
│  ─────    │                                  │   threat: ■■■□□      │
│  [관계망]  │                                  │   pressure: ■■□□□    │
│  [What-If] │                                  │   resource: ■■■■□    │
│           │                                  │                      │
├───────────┴──────────────────────────────────┴───────────────────────┤
│  피드: 소셜 미디어 / 인텔리전스            │  타임라인 [R1][R2][R3⚡]… │
│  @user_CN: "남중국해 훈련은 정당한..."     │   ▲ 스크러버              │
│  @user_US: "동맹국 방어 의지 재확인..."    │                          │
└────────────────────────────────────────────┴──────────────────────────┘
```

#### 페이즈별 UI 상태

| 페이즈 | 맵 상태 | 오버레이 | 피드 | 색온도 |
|--------|---------|---------|------|--------|
| 시뮬레이션 실행 | 실시간 에이전트 활동 애니메이션 | 없음 | 실시간 스크롤 | Cool (블루) |
| 브리핑 | 이벤트 마커 하이라이트 | 브리핑 카드 (반투명) | 이번 라운드 요약 | Neutral |
| 결정 대기 | 결정 관련 지역 하이라이트 | 결정 카드 (중앙) | 관련 피드 필터링 | Warm (앰버) |
| 확정/전환 | 결정 결과 반영 애니메이션 | "결정 반영됨" 토스트 | 전체 피드 | Neutral |

#### 페이즈 전환 로직

```typescript
// frontend/src/hooks/useWargame.ts (신규)

type WargamePhase = "simulation" | "briefing" | "decision" | "confirmation";

interface WargameState {
  phase: WargamePhase;
  round: number;
  totalRounds: number;
  role: "actor_role" | "game_master";
  actorId: string | null;
  briefing: RoundBriefing | null;
  decisionPoint: DecisionPoint | null;
  tension: number;
  actorStates: Record<string, ActorState>;
}

function useWargame(scenarioId: string) {
  // SSE 연결
  useEffect(() => {
    const es = new EventSource(`/api/scenario/${scenarioId}/events`);

    es.addEventListener("phase_change", (e) => {
      const data = JSON.parse(e.data);
      setPhase(data.phase);
      setRound(data.round);
    });

    es.addEventListener("decision_required", (e) => {
      const data = JSON.parse(e.data);
      setPhase("briefing");
      setBriefing(data.briefing);
      setDecisionPoint(data.decision_point);
    });

    es.addEventListener("round_complete", (e) => {
      const data = JSON.parse(e.data);
      updateRoundStats(data);
    });

    return () => es.close();
  }, [scenarioId]);
}
```

#### 기존 탭 → 새 구조 매핑

| 기존 탭 | 새 위치 | 형태 |
|---------|--------|------|
| Progress | 상단 페이즈 바 | 라운드 카운터 + 페이즈 인디케이터 |
| Interactive | 삭제 | 전체 경험이 인터랙티브 |
| Decisions | Phase 3 오버레이 | 결정 카드 자동 표시 |
| Geopolitics | 렌즈 (외교/군사) + 브리핑 | 맵 오버레이 + Phase 2 브리핑 카드 |
| Graph | 좌측 렌즈 [관계망] | 맵 오버레이 또는 사이드 패널 |
| Timeline | 하단 타임라인 바 | 항상 표시, 라운드 마커 + 스크러버 |
| What-If | 좌측 렌즈 [What-If] | 특정 라운드에서 분기 생성 |
| Report | 게임 종료 후 디브리프 화면 | 전체 완료 시에만 표시 |
| LiveActionFeed | 하단 피드 패널 | 항상 표시, 소셜 미디어 피드 |
| LiveStats | 상단 바에 통합 | Round N/M + Tension 게이지 |

#### 결정 카드 상세

```
┌──────────────────────────────────────────────┐
│  ⚠️  외교 위기 — Round 3                       │
│                                              │
│  "중국 해군이 남중국해에서 대규모 군사훈련을      │
│   선포했습니다. 필리핀이 미국의 지원을            │
│   요청하고 있습니다."                           │
│                                              │
│  ┌────────────────────────────────────────┐  │
│  │ 🔴 군사 대응                  (엔진 추천) │  │
│  │ 합동 순찰 강화                           │  │
│  │ → 긴장도 ↑15%, 동맹 신뢰 ↑10%           │  │
│  │ 📊 외교장관: "확전 위험이 있습니다"        │  │
│  ├────────────────────────────────────────┤  │
│  │ 🟡 외교적 대응                           │  │
│  │ UN 안보리 긴급회의 요청                   │  │
│  │ → 긴장도 ↓5%, 시간 소요 ↑                │  │
│  │ 📊 국방장관: "너무 느립니다"               │  │
│  ├────────────────────────────────────────┤  │
│  │ 🟢 경제적 대응                           │  │
│  │ 대중국 반도체 수출 제한                    │  │
│  │ → 무역 수입 ↓20%, 기술 우위 ↑            │  │
│  │ 📊 재무장관: "보복 관세가 우려됩니다"       │  │
│  ├────────────────────────────────────────┤  │
│  │ ⚪ 현상 유지                             │  │
│  │ 상황 관망                                │  │
│  │ → 동맹 신뢰 ↓10%, 국내 여론 ↓5%          │  │
│  │ 📊 안보보좌관: "약해 보일 수 있습니다"      │  │
│  └────────────────────────────────────────┘  │
│                                              │
│        [ 결정 확정 ]     [ What-If 분기 ]      │
└──────────────────────────────────────────────┘
```

#### 브리핑 화면 (Phase 2)

```
┌──────────────────────────────────────────────────────────┐
│  📋 ROUND 3 브리핑                                        │
│                                                          │
│  ┌─ 핵심 이벤트 ──────────────────────────────────────┐  │
│  │ 🔴 군사 이동: 중국 해군 3함대, 남중국해 진입         │  │
│  │ 🟡 외교 성명: 필리핀 대통령, 상호방위조약 발동 촉구   │  │
│  │ 🟢 경제: ASEAN 무역 회의 연기 발표                   │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  ┌─ 상태 변화 (vs 이전 라운드) ────────────────────────┐  │
│  │ 긴장도:     ■■■■□ 0.72  (↑ 0.15)                   │  │
│  │ 국내 압력:   ■■■□□ 0.55  (↑ 0.05)                   │  │
│  │ 자원 수준:   ■■■■□ 0.80  (→ 변동 없음)              │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  ┌─ 지난 결정 결과 ────────────────────────────────────┐  │
│  │ Round 2에서 "외교적 대응" 선택                       │  │
│  │ → 중국: 긴장도 소폭 하락 (-0.05)                    │  │
│  │ → 동맹국: "미국의 신중한 대응에 실망" (신뢰 ↓0.05)   │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  ┌─ 소셜 미디어 요약 ──────────────────────────────────┐  │
│  │ 트윗 42건 (전 라운드 대비 +18)                       │  │
│  │ 주요 화제: 군사훈련(28건), 동맹(9건), 제재(5건)       │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│              [ 브리핑 확인 → 결정 단계로 ]                 │
└──────────────────────────────────────────────────────────┘
```

#### 디브리프 / 애프터액션 리뷰 (게임 종료 후)

```
┌──────────────────────────────────────────────────────────┐
│  📊 시뮬레이션 디브리프                                    │
│                                                          │
│  타임라인:                                                │
│  [R1]──[R2]──[R3 ⚡결정]──[R4]──[R5 ⚡결정]──[R6]──[R7]──[R8] │
│              ↑ 스크러버                                    │
│                                                          │
│  결정 마커(⚡) 클릭 시:                                    │
│  · 당시 선택지 + 실제 선택 표시                            │
│  · 결정 전후 상태 변화                                     │
│  · [What-If 분기] 버튼 → 다른 선택으로 재시뮬레이션         │
│                                                          │
│  ┌─ 긴장도 곡선 ────────────────────────────────────────┐ │
│  │  (Recharts: 라운드별 긴장도 + 결정 마커)              │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                          │
│  ┌─ 최종 상태 요약 ────────────────────────────────────┐  │
│  │  총 라운드: 8  |  결정 횟수: 2  |  최종 긴장도: 0.45  │  │
│  │  주요 이벤트: 군사훈련 2회, 제재 1회, 조약 1회        │  │
│  └───────────────────────────────────────────────────────┘ │
│                                                          │
│  [ 전체 리포트 보기 ]  [ 새 시뮬레이션 ]  [ What-If 분기 ]  │
└──────────────────────────────────────────────────────────┘
```

### 3.9 수정 대상 파일 요약

```
# MiroFish 수정 (external/)
external/mirofish-backend/scripts/run_parallel_simulation.py  # 라운드 배리어 + IPC
external/mirofish-backend/scripts/run_twitter_simulation.py   # 시스템 포스트 주입
external/mirofish-backend/scripts/run_reddit_simulation.py    # 시스템 포스트 주입

# Backend 신규
backend/app/services/context_injection.py       # 컨텍스트 주입 엔진
backend/app/routers/simulation_events.py        # SSE 실시간 이벤트 스트림

# Backend 수정
backend/app/models/scenario.py                  # wargame_enabled, wargame_idle_ttl_minutes
backend/app/services/simulation_orchestrator.py # run_wargame_pipeline, _continue_wargame
backend/app/services/geopolitics_mapper.py      # 출처 태깅 + 디바운스
backend/app/routers/simulation_run.py           # 워게임 모드 라우팅
backend/app/database.py                         # wargame_state 테이블

# Frontend 신규
frontend/src/hooks/useWargame.ts                # 워게임 상태 관리 + SSE
frontend/src/components/wargame/WarRoom.tsx      # 메인 상황실 레이아웃
frontend/src/components/wargame/PhaseBar.tsx     # 상단 페이즈 인디케이터
frontend/src/components/wargame/LensPanel.tsx    # 좌측 렌즈 선택 패널
frontend/src/components/wargame/ContextPanel.tsx # 우측 컨텍스트 패널
frontend/src/components/wargame/FeedPanel.tsx    # 하단 피드 + 타임라인
frontend/src/components/wargame/BriefingOverlay.tsx  # Phase 2 브리핑 오버레이
frontend/src/components/wargame/DecisionCard.tsx     # Phase 3 결정 카드
frontend/src/components/wargame/DebriefView.tsx      # 게임 종료 디브리프
frontend/src/components/wargame/RoundTimeline.tsx    # 하단 타임라인 바 + 스크러버
frontend/src/lib/api/wargameApi.ts                   # 워게임 전용 API 클라이언트

# Frontend 수정
frontend/src/components/simulation/SimulationPanel.tsx  # wargame_enabled 시 WarRoom으로 분기
frontend/src/types/simulation.ts                        # WargamePhase, WargameState 타입
```

---

## 4. 마일스톤

### M1: IPC Round Control Protocol

MiroFish `run_parallel_simulation.py`에 라운드 배리어를 추가한다. `round_control_enabled=true`일 때 매 라운드 시작 전 stdin에서 `proceed` 신호를 기다리고, 라운드 완료 후 stdout으로 `round_complete` + 액션을 전송한다. stderr로 로그를 분리한다.

- 검증: `round_control_enabled=false`로 기존 시뮬레이션 실행 → 동작 동일 (regression 없음). `round_control_enabled=true`로 실행 → stdin/stdout에서 제어 메시지 왕복 확인. 3라운드 시뮬레이션을 1라운드씩 수동 proceed하여 전체 완료 확인.

### M2: 컨텍스트 주입 엔진

`context_injection.py` 구현. 지정학 이벤트와 사용자 결정을 시스템 포스트로 변환. MiroFish의 `_inject_context_to_env()`로 OASIS 환경에 포스트 삽입.

- 검증: 테스트 이벤트(military_movement)를 변환 → 시스템 포스트 구조 확인. OASIS 환경에 포스트 삽입 후 에이전트 피드에 노출 확인.

### M3: 피드백 폭주 방지

`geopolitics_mapper.py`에 출처 필터 + 라운드당 디바운스 추가. 시스템 포스트에서 발생한 에이전트 반응(`source: geo_event`)이 다음 라운드 지정학 매핑에서 제외되는지 확인.

- 검증: 시스템 포스트 주입 → 에이전트 반응 → `map_actions_to_geopolitics()` 호출 → geo_event 출처 액션 필터링 확인. 동일 이벤트 타입이 라운드당 1회만 생성되는지 확인.

### M4: Orchestrator Wargame Coordinator

`run_wargame_pipeline()` 구현. Phase 0(기존 파이프라인) → Phase 1(MiroFish 시작) → Phase 2(라운드 루프) → Phase 3(완료). `_continue_wargame()` 재개 로직. 프로세스 수명 관리(하트비트, TTL).

- 검증: `wargame_enabled=true`로 시뮬레이션 시작 → 라운드별 proceed/round_complete 순환 확인. should_pause() 트리거 → Decision Point 생성 → 결정 후 재개 → 나머지 라운드 완료. `wargame_enabled=false` → 기존 run_pipeline() 동작 동일.

### M5: SSE 실시간 이벤트 스트림

`simulation_events.py` 구현. 워게임 루프의 페이즈 전환, 라운드 완료, 결정 요청 등을 SSE로 프론트엔드에 푸시.

- 검증: SSE 연결 후 라운드 실행 → `round_complete` 이벤트 수신 확인. should_pause() 트리거 → `decision_required` 이벤트 수신 확인.

### M6: 프론트엔드 상황실 기본 레이아웃

`WarRoom.tsx`, `PhaseBar.tsx`, `LensPanel.tsx`, `ContextPanel.tsx`, `FeedPanel.tsx` 구현. `useWargame.ts` SSE 훅. `SimulationPanel.tsx`에서 `wargame_enabled` 분기.

- 검증: 워게임 모드 시뮬레이션 시작 → 상황실 레이아웃 렌더링. 페이즈 바에 현재 페이즈 표시. 맵 + 렌즈 + 컨텍스트 패널 + 피드 4영역 정상 렌더링.

### M7: 프론트엔드 브리핑 + 결정 카드

`BriefingOverlay.tsx`, `DecisionCard.tsx` 구현. SSE `decision_required` 수신 시 자동 페이즈 전환: 시뮬레이션 → 브리핑 → 결정.

- 검증: should_pause() 트리거 → 브리핑 오버레이 자동 표시 → "결정 단계로" 클릭 → 결정 카드 표시 → 선택 + 확정 → 시뮬레이션 재개.

### M8: 프론트엔드 디브리프 + 타임라인

`DebriefView.tsx`, `RoundTimeline.tsx` 구현. 타임라인 스크러빙으로 과거 라운드 상태 확인. 결정 마커 클릭으로 당시 선택지 + 결과 확인. What-If 분기 버튼 연결.

- 검증: 전체 시뮬레이션 완료 → 디브리프 화면 자동 표시. 타임라인 스크러빙 → 해당 라운드 상태 표시. 결정 마커 클릭 → 결정 상세 팝업. What-If 분기 → 기존 WhatIfEngine 호출 확인.

### M9: 통합 테스트

전체 워게임 루프 E2E: 시나리오 생성 → 워게임 모드 시작 → 3라운드 이상 실행 → 최소 1회 결정 포인트 → 결정 후 재개 → 에이전트가 시스템 포스트에 반응하는지 확인 → 완료 → 디브리프.

- 검증: 위 시나리오 전체 통과. `wargame_enabled=false`로 기존 파이프라인 regression 없음. 프로세스 크래시 시뮬레이션 → 재시작 후 마지막 라운드부터 재개 확인.

---

## 5. 성공 기준

- `wargame_enabled=false` 시 기존 동작과 100% 동일하다 (regression 없음)
- 사용자의 전략적 결정(제재, 군사 대응 등)이 시스템 포스트로 에이전트 피드에 주입된다
- 에이전트가 시스템 포스트에 반응하여 다음 라운드 행동이 달라진다 (결정 전/후 비교로 검증)
- 지정학 이벤트가 매 라운드 후 실시간으로 생성되어 사용자에게 표시된다
- 결정 카드에 선택지별 예측 결과(PROPAGATION_RULES 기반)가 표시된다
- 피드백 폭주가 발생하지 않는다 (시스템 포스트 출처 액션은 지정학 매핑에서 제외)
- 일시정지 후 30분 TTL 내에 결정하지 않으면 자동으로 나머지 라운드가 진행된다
- 프론트엔드가 페이즈 기반 상황실로 동작한다 (탭 네비게이션 없음)
- SSE로 페이즈 전환이 실시간으로 반영된다 (폴링 5초 지연 없음)
- 디브리프 타임라인에서 과거 라운드의 상태와 결정을 스크러빙으로 확인할 수 있다

---

## 6. 위험 및 완화

| 위험 | 심각도 | 완화 |
|------|--------|------|
| OASIS 환경에 시스템 포스트 삽입 API가 없을 수 있음 | High | M2에서 즉시 확인. 없으면 OASIS DB에 직접 INSERT하거나, 전용 "시스템 에이전트"를 생성하여 포스트 |
| 에이전트가 시스템 포스트를 무시할 수 있음 (LLM 판단) | Medium | 시스템 포스트의 프레이밍을 "속보" / "공식 성명" 등으로 강화. 에이전트 프롬프트에 "뉴스와 공식 발표에 주의"를 추가할 수 있으나 최후 수단 |
| stdout에 로그 오염 시 IPC 파싱 실패 | High | stderr로 로그 분리를 M1에서 강제. OASIS, LiteLLM 등 서드파티 라이브러리의 stdout 출력을 리다이렉트 |
| 피드백 폭주 방지 로직 우회 | Medium | 출처 태깅이 누락되는 엣지 케이스 발생 시 라운드당 이벤트 수 상한(max 10)으로 보조 |
| 프로세스 장기 유휴로 메모리 누수 | Low | TTL 30분 + 하트비트로 관리. TTL 초과 시 깨끗하게 종료 |
| 에이전트 맥락 손실 (프로세스 재시작) | Medium | v11에서는 감수. 지정학 상태 + 이벤트 히스토리는 DB에 보존되어 시뮬레이션 연속성 유지. 향후 Zep 그래프 메모리로 에이전트 맥락 영속화 (v12) |
| SSE 연결 끊김 | Low | 프론트엔드에서 자동 재연결 + 마지막 수신 이벤트 이후 상태 폴백 |
| 시뮬레이션 라운드 수가 적으면 (3~5) 워게임 효과 미미 | Medium | 기본 라운드 수를 8~10으로 상향 권장. `max_rounds` 파라미터로 사용자 조정 가능 |
| 프론트엔드 상황실 UI가 기존 대시보드 기능(OSINT 패널 등)과 충돌 | Medium | 워게임 모드는 별도 `WarRoom` 컴포넌트로 분리. 기존 `SimulationPanel`은 `wargame_enabled=false` 시 그대로 유지 |

---

## 진행 로그

| 날짜 | 상태 | 내용 |
|------|------|------|
| 2026-03-31 | Draft | v11 워게임 루프 PRD 초안. Oracle 아키텍처 검증 완료. 외교 시뮬레이션 UX 리서치 (Paradox, RAND, Palantir, Battleplan, XCOM, Statecraft, Suzerain) 반영. |

---

## PRD 인덱스

| PRD | 설명 | 상태 |
|-----|------|------|
| [v11-backend-wargame-engine.md](prds/v11-backend-wargame-engine.md) | 백엔드 워게임 엔진 (M1~M5: IPC, 컨텍스트 주입, 폭주 방지, 오케스트레이터, SSE) | Draft |
| [v11-frontend-war-room.md](prds/v11-frontend-war-room.md) | 프론트엔드 상황실 War Room (M6~M8: 레이아웃, 브리핑/결정 카드, 디브리프/타임라인) | Draft |
