# PRD: 백엔드 워게임 엔진

> Status: Draft
> Created: 2026-03-31
> Dependencies: v9-interactive-geopolitics (DecisionEngine, snapshots), v4-interactive-simulation (DecisionPoint, checkpoint)
> 관련 스펙: [v11-wargame-loop/spec.md](../spec.md) 섹션 3.1~3.7
> 버전: v11.1

---

## 1. 문제 정의

V11 스펙의 워게임 루프를 구현하기 위한 백엔드 인프라. MiroFish 라운드 제어, 컨텍스트 주입, 피드백 폭주 방지, 오케스트레이터 워게임 코디네이터, SSE 실시간 이벤트 스트림을 포함한다.

### 범위

스펙의 마일스톤 M1~M5에 해당:

| 마일스톤 | 내용 | 수정 대상 |
|----------|------|----------|
| M1 | IPC Round Control Protocol | `external/mirofish-backend/scripts/run_parallel_simulation.py` |
| M2 | 컨텍스트 주입 엔진 | `backend/app/services/context_injection.py` (신규) |
| M3 | 피드백 폭주 방지 | `backend/app/services/geopolitics_mapper.py` |
| M4 | Orchestrator Wargame Coordinator | `backend/app/services/simulation_orchestrator.py`, `backend/app/models/scenario.py`, `backend/app/database.py` |
| M5 | SSE 실시간 이벤트 스트림 | `backend/app/routers/simulation_events.py` (신규) |

### 제약 조건

- `wargame_enabled=false` 시 기존 동작 100% 호환
- OASIS `env.step()`은 atomic — 라운드 내부 개입 불가
- stderr=로그, stdout=제어 메시지 분리 필수
- 에이전트 메모리 in-process — 프로세스 유지 필수 (TTL 30분)

---

## 2. 기술 상세

스펙 섹션 3.1~3.7의 구현 상세. 각 마일스톤별로 수정 파일, 핵심 변경, 검증 기준을 명시한다.

### M1: IPC Round Control Protocol

**수정 파일:**
- `external/mirofish-backend/scripts/run_parallel_simulation.py`
- `external/mirofish-backend/scripts/run_twitter_simulation.py`
- `external/mirofish-backend/scripts/run_reddit_simulation.py`

**핵심 변경:**

1. `_send_control(msg)`: stdout으로 NDJSON 제어 메시지 전송. 기존 print/logging을 전부 stderr로 리다이렉트.
2. `_wait_for_control_signal()`: stdin에서 NDJSON 대기. `asyncio.run_in_executor`로 블로킹 readline 래핑.
3. 라운드 루프에 배리어 삽입: `round_control_enabled=True`면 매 라운드 시작 전 `proceed` 대기, 완료 후 `round_complete` 전송.
4. `simulation_config.json`에 `round_control_enabled` 필드 추가.
5. 서드파티 라이브러리(OASIS, LiteLLM 등)의 stdout 출력을 stderr로 리다이렉트.

**NDJSON 프로토콜**: 스펙 3.1의 7개 메시지 타입 (ready, proceed, round_complete, stop, error, heartbeat, heartbeat_ack) 구현.

**검증:**
- `round_control_enabled=false` → 기존 시뮬레이션 동작 동일 (regression 없음)
- `round_control_enabled=true` → stdin에서 `{"type":"proceed","round":1}` 전송 → stdout에서 `{"type":"round_complete","round":1,"actions":[...]}` 수신
- 3라운드를 1라운드씩 수동 proceed → 전체 완료
- stdout에 로그 오염 없음 (stderr만 로그)

### M2: 컨텍스트 주입 엔진

**신규 파일:**
- `backend/app/services/context_injection.py`

**핵심 변경:**

1. `EVENT_POST_TEMPLATES`: 6개 이벤트 타입별 시스템 포스트 템플릿 (military_movement, military_exercise, sanction_impose, trade_restriction, diplomatic_statement, treaty_sign)
2. `DECISION_POST_TEMPLATES`: 사용자 결정 타입별 시스템 포스트 템플릿
3. `build_inject_context(engine, round_result, user_decision)`: 지정학 라운드 결과 + 사용자 결정 → `inject_context` 구조 생성
4. 모든 시스템 포스트에 `metadata.source` 태그 부착 (피드백 폭주 방지용)

**MiroFish 측 주입:**
- `_inject_context_to_env(env, context)`: OASIS 환경에 시스템 포스트 생성. `env.create_system_post()` API 존재 여부 먼저 확인 — 없으면 OASIS DB 직접 INSERT 또는 시스템 에이전트 방식으로 폴백.

**검증:**
- military_movement 이벤트 → 시스템 포스트 구조 생성 확인 (author, content, metadata)
- 사용자 "do_nothing" 결정 → 포스트 미생성
- OASIS 환경에 포스트 삽입 후 에이전트 피드에 노출 확인

### M3: 피드백 폭주 방지

**수정 파일:**
- `backend/app/services/geopolitics_mapper.py`

**핵심 변경:**

1. `map_actions_to_geopolitics(actions, source_filter)`: 출처 태깅 필터 추가
2. `metadata.source == "geo_event"` 액션 → 지정학 매핑에서 제외
3. `metadata.source == "user_decision"` 액션 → 지정학 매핑에서 제외 (엔진에 이미 반영)
4. 라운드당 디바운스: 동일 이벤트 타입은 라운드당 1회만 생성

**검증:**
- 시스템 포스트 주입 → 에이전트 반응 → `map_actions_to_geopolitics()` 호출 → `source: geo_event` 액션 필터링 확인
- 동일 이벤트 타입 3개 액션 → 1개만 매핑 (디바운스)

### M4: Orchestrator Wargame Coordinator

**수정 파일:**
- `backend/app/services/simulation_orchestrator.py`
- `backend/app/models/scenario.py`
- `backend/app/routers/simulation_run.py`
- `backend/app/database.py`

**핵심 변경:**

1. `SimulationParams`에 `wargame_enabled: bool = False`, `wargame_idle_ttl_minutes: int = 30` 추가
2. `wargame_state` DB 테이블 생성 (id, scenario_id, result_id, current_round, total_rounds, engine_state, process_pid, status, last_heartbeat)
3. `run_wargame_pipeline()`: Phase 0(기존 파이프라인) → Phase 1(MiroFish round_control 시작) → Phase 2(라운드 루프) → Phase 3(완료). 스펙 3.2 구현.
4. `_continue_wargame()`: 일시정지에서 재개. 스냅샷 복원 → 결정 반영 → 나머지 라운드 루프.
5. `_start_heartbeat_loop()`: TTL 30분 + 하트비트 30초 간격. TTL 초과 시 프로세스 종료 + 자동 완료.
6. `simulation_run.py`에서 `wargame_enabled=True`면 `run_wargame_pipeline()`, `False`면 기존 `run_pipeline()` 호출.

**검증:**
- `wargame_enabled=true`로 시뮬레이션 시작 → 라운드별 proceed/round_complete 순환
- should_pause() 트리거 → Decision Point 생성 → 상태 `wargame:paused:round_N`
- 결정 후 재개 → 나머지 라운드 완료
- `wargame_enabled=false` → 기존 run_pipeline() 동작 동일

### M5: SSE 실시간 이벤트 스트림

**신규 파일:**
- `backend/app/routers/simulation_events.py`

**의존성:** `sse-starlette` 패키지 (uv add)

**핵심 변경:**

1. `GET /api/scenario/{scenario_id}/events`: SSE 엔드포인트. EventSourceResponse 반환.
2. 이벤트 버스: asyncio 기반 pub/sub. 오케스트레이터가 `emit()`, SSE가 `subscribe()`.
3. 이벤트 타입 6종: `phase_change`, `round_complete`, `decision_required`, `decision_resolved`, `round_stats`, `simulation_complete`
4. `main.py`에 라우터 등록.

**검증:**
- SSE 연결 후 라운드 실행 → `round_complete` 이벤트 수신
- should_pause() → `decision_required` 이벤트 수신
- 연결 끊김 후 재연결 → 정상 동작

---

## 3. 수정 대상 파일 요약

```
# MiroFish (M1)
external/mirofish-backend/scripts/run_parallel_simulation.py
external/mirofish-backend/scripts/run_twitter_simulation.py
external/mirofish-backend/scripts/run_reddit_simulation.py

# Backend 신규 (M2, M5)
backend/app/services/context_injection.py
backend/app/routers/simulation_events.py

# Backend 수정 (M3, M4)
backend/app/services/geopolitics_mapper.py
backend/app/services/simulation_orchestrator.py
backend/app/models/scenario.py
backend/app/routers/simulation_run.py
backend/app/database.py
backend/app/main.py
```

---

## 4. 구현 순서

M1 → M2 → M3 → M4 → M5 (순차적 의존성)

- M1이 없으면 M4(오케스트레이터)가 MiroFish를 제어할 수 없음
- M2가 없으면 M4가 컨텍스트를 주입할 수 없음
- M3가 없으면 피드백 폭주로 시뮬레이션이 발산
- M5는 M4와 병렬 가능하나, M4의 이벤트 emit이 먼저 구현되어야 SSE가 의미 있음

---

## 5. 성공 기준

- `wargame_enabled=false` 시 기존 동작 100% 동일 (regression 없음)
- 워게임 루프에서 에이전트가 시스템 포스트에 반응하여 행동 변화 확인
- 피드백 폭주 미발생 (시스템 포스트 출처 액션은 지정학 매핑 제외)
- 일시정지 TTL 30분 초과 시 자동 완료
- SSE로 페이즈 전환 실시간 수신

---

## 6. 위험 및 완화

| 위험 | 완화 |
|------|------|
| OASIS 시스템 포스트 API 부재 | M2에서 즉시 확인. 없으면 DB 직접 INSERT 또는 시스템 에이전트 방식 |
| stdout 로그 오염 | M1에서 모든 로깅을 stderr로 강제. 서드파티 라이브러리 stdout 리다이렉트 |
| 피드백 폭주 방지 로직 우회 | 출처 태깅 누락 시 라운드당 이벤트 수 상한(max 10) 보조 |
| 프로세스 장기 유휴 메모리 누수 | TTL + 하트비트. 초과 시 깨끗하게 종료 |
| sse-starlette 의존성 추가 | FastAPI 공식 권장. 경량 라이브러리 |

---

## 진행 로그

| 날짜 | 상태 | 내용 |
|------|------|------|
| 2026-03-31 | Draft | v11.1 백엔드 워게임 엔진 PRD 작성 |
