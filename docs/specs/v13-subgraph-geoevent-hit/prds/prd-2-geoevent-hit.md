# PRD-2: 지정학 이벤트 HIT

> Phase: 2 / 3
> Status: Completed
> 선행 조건: PRD-1 완료 (서브그래프 분리, State 확장)
> 참조: v13-spec.md §2.3 (HIT 트리거 기준), §3.3 (evaluate_events_node)

---

## 목표

`check_intervention_node`를 `evaluate_events_node`로 교체하여, DecisionEngine이 생성하는 지정학 이벤트(캐스케이드, 고강도 군사 행동)에 반응하여 HIT interrupt를 트리거한다.

**이 Phase가 끝나면**: 캐스케이드 이벤트 발생 → interrupt() → 프론트에 DecisionCard 표시 → 사용자 결정 → 시뮬레이션 재개. 기존 긴장도/방향 체크포인트도 유지.

---

## M1: evaluate_events_node 구현

### 작업

1. `simulation-service/app/graph/nodes/intervene.py` 재작성:
   - `check_intervention_node` 제거
   - `evaluate_events_node` 신규 — 4단계 우선순위 트리거:

| 우선순위 | 트리거 | 조건 | payload `trigger` |
|---------|--------|------|-------------------|
| 1 | 캐스케이드 반응 | `round_cascades` >= 1건 | `cascade_reaction` |
| 2 | 고강도 군사 | `military_movement`/`deploy_forces`/`cyber_operation`, magnitude >= 0.7 | `high_intensity_military` |
| 3 | 긴장도 임계값 | max tension >= 0.6 | `tension_threshold_exceeded` |
| 4 | 방향 체크포인트 | `_is_direction_round()` | `direction_checkpoint` |

2. 쿨다운 메커니즘:
   - 이벤트 트리거(1, 2)는 `hit_trigger.round` 기준 2라운드 미경과 시 스킵
   - 긴장도/방향 트리거(3, 4)는 쿨다운 무관 — 항상 검사

3. interrupt payload에 `trigger_detail` 추가:
   - `event_type`, `source_actor`, `target_actors`, `magnitude`, `description`
   - 캐스케이드인 경우 `cascade_chain`: `[{from, to, depth}]`
   - `actor_states_snapshot`: 현재 행위자 상태

4. 헬퍼 함수들:
   - `_build_event_interrupt()` — 이벤트 기반 interrupt payload 빌드
   - `_build_tension_interrupt()` — 긴장도 interrupt payload 빌드
   - `_build_direction_interrupt()` — 기존 방향 체크포인트 payload (trigger/trigger_detail 필드 추가)
   - `_last_hit_round()` — 마지막 HIT 라운드 번호 조회
   - `should_continue()` — 기존 유지 (complete/apply_decision/continue)

### 결과물

| 파일 | 상태 |
|------|------|
| `simulation-service/app/graph/nodes/intervene.py` | 재작성 |

### 성공 기준

- 캐스케이드 이벤트 발생 라운드에서 interrupt() 호출
- 고강도 군사 행동(magnitude >= 0.7) 시 interrupt() 호출
- 쿨다운 2라운드 내 이벤트 트리거 스킵 (긴장도/방향은 예외)
- interrupt payload에 `trigger`, `trigger_detail` 포함

---

## M2: apply_decision_node 이벤트 필드 정리

### 작업

1. `simulation-service/app/graph/nodes/decision.py` 수정:
   - 결정 적용 후 `round_events: []`, `round_cascades: []` 반환
   - 이전 라운드 이벤트가 다음 라운드에 잔존하는 것 방지

### 결과물

| 파일 | 상태 |
|------|------|
| `simulation-service/app/graph/nodes/decision.py` | 수정 |

### 성공 기준

- 결정 적용 후 다음 run_round 진입 시 `round_events`, `round_cascades` 빈 리스트

---

## M3: SSE geopolitical_event 발행

### 작업

1. `simulation-service/app/services/event_emitter.py` — `emit_geopolitical_event()` 추가:
   - `type: "geopolitical_event"`
   - `scenario_id`, `round`, `trigger_type`, `events` (최대 5건)
   - 페이로드 제한: 기존 `_PAYLOAD_LIMIT` + `event_ref` 로직이 자동 대응

2. `simulation-service/app/graph/nodes/results.py` — `calculate_results_node`에서 호출:
   - `round_events` 또는 `round_cascades`가 있을 때만 발행
   - `trigger_type`: 캐스케이드면 `"cascade_reaction"`, 아니면 `"round_events"`

### 결과물

| 파일 | 상태 |
|------|------|
| `simulation-service/app/services/event_emitter.py` | 수정 |
| `simulation-service/app/graph/nodes/results.py` | 수정 (M1에서 이미 수정, 여기서 emit 추가) |

### 성공 기준

- 이벤트 발생 라운드에서 SSE `geopolitical_event` 메시지가 Gateway → 프론트까지 전달
- pg_notify 8KB 초과 시 `event_ref` 폴백 동작

---

## 구현 메모

- `HIGH_INTENSITY_TYPES = {"military_movement", "deploy_forces", "cyber_operation"}` — engine/events.py의 CASCADE_RULES 및 PROPAGATION_RULES와 일관
- `HIT_COOLDOWN_ROUNDS = 2` — 너무 잦은 HIT 방지. 추후 시나리오 파라미터로 조절 가능
- 기존 `DIRECTION_OPTIONS` 리스트는 변경 없이 재사용
- `_build_direction_interrupt()`에 `trigger: "direction_checkpoint"`, `trigger_detail: None` 추가 — 프론트에서 트리거 유형을 일관되게 처리
