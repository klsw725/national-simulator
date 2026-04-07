# PRD-3: 프론트엔드 통합

> Phase: 3 / 3
> Status: Completed
> 선행 조건: PRD-2 완료 (evaluate_events_node, SSE geopolitical_event)
> 참조: v13-spec.md §4 (프론트엔드 변경 상세)

---

## 목표

프론트엔드에서 신규 SSE 이벤트(`geopolitical_event`)를 수신하고, DecisionCard에 HIT 트리거 맥락을, ContextPanel에 이벤트 배지를, FeedPanel에 캐스케이드 하이라이트를 표시한다.

**이 Phase가 끝나면**: 지정학 이벤트 기반 HIT 시 사용자가 "왜 중단되었는지"를 즉시 파악 가능. 캐스케이드 연쇄가 시각적으로 표현됨.

---

## M1: 타입 + SSE 리스너

### 작업

1. `frontend/src/types/simulation-stream.ts` — 타입 추가:
   - `CascadeChainEntry`: `{ from: string; to: string; depth: number }`
   - `TriggerDetail`: `{ event_type, source_actor, target_actors, magnitude, description, cascade_chain? }`
   - `GeopoliticalEventPayload`: `{ round, trigger_type, events[] }`
   - `DecisionPointV2.trigger_detail?: TriggerDetail | null` 필드 추가
   - `SimulationStreamState.latestGeopoliticalEvent: GeopoliticalEventPayload | null` 필드 추가
   - `SimulationStreamAction` union에 `GEOPOLITICAL_EVENT` 추가

2. `frontend/src/hooks/useSimulationStream.ts` — SSE 리스너:
   - `INITIAL_STATE`에 `latestGeopoliticalEvent: null`
   - reducer `GEOPOLITICAL_EVENT` case 추가
   - `es.addEventListener("geopolitical_event", ...)` 등록

### 결과물

| 파일 | 상태 |
|------|------|
| `frontend/src/types/simulation-stream.ts` | 수정 |
| `frontend/src/hooks/useSimulationStream.ts` | 수정 |

### 성공 기준

- SSE `geopolitical_event` 수신 시 `streamState.latestGeopoliticalEvent` 업데이트
- 기존 이벤트(phase_change, agent_action 등) 동작 영향 없음

---

## M2: DecisionCard 트리거 맥락

### 작업

1. `frontend/src/components/wargame/DecisionCard.tsx` — 트리거 배너 추가:
   - 신규 prop: `triggerInfo?: { trigger: string; trigger_detail?: TriggerDetail | null } | null`
   - `TriggerBanner` 컴포넌트: 헤더와 내러티브 사이에 삽입
   - 트리거 유형별 스타일:

| trigger | 라벨 | 배경 | 보더 |
|---------|------|------|------|
| `cascade_reaction` | 연쇄 반응 감지 | `rgba(239,68,68,0.08)` | `#ef4444` |
| `high_intensity_military` | 고강도 군사 행동 | `rgba(239,68,68,0.08)` | `#ef4444` |
| `tension_threshold_exceeded` | 긴장도 임계값 초과 | `rgba(245,158,11,0.08)` | `#f59e0b` |
| `direction_checkpoint` | 방향 체크포인트 | `rgba(107,114,128,0.08)` | `#6b7280` |

   - `cascade_chain` 존재 시: `from → to` 체인을 모노스페이스로 렌더링
   - `trigger_detail.description` 표시

2. `frontend/src/components/wargame/WarRoom.tsx` — prop 전달:
   - `triggerInfo`를 `activeDecisionPoint`에서 추출하여 DecisionCard에 전달
   - `trigger_detail`은 `DecisionPointV2`에만 존재 — 타입 안전 접근 (`as` cast)

### 결과물

| 파일 | 상태 |
|------|------|
| `frontend/src/components/wargame/DecisionCard.tsx` | 수정 |
| `frontend/src/components/wargame/WarRoom.tsx` | 수정 |

### 성공 기준

- 이벤트 기반 HIT 시 DecisionCard에 트리거 배너 표시
- 기존 방향 체크포인트/긴장도 HIT 시에도 적절한 배너 표시
- `trigger`/`trigger_detail` 없는 레거시 결정 포인트에서 배너 미표시 (graceful)

---

## M3: ContextPanel 이벤트 배지 + FeedPanel 캐스케이드 하이라이트

### 작업

1. `frontend/src/components/wargame/ContextPanel.tsx`:
   - 신규 prop: `geopoliticalEvent?: GeopoliticalEventPayload | null`
   - 이벤트 배지 섹션: 위상 배지와 행위자 카드 사이에 삽입
   - `rgba(239,68,68,0.06)` 배경, `rgba(239,68,68,0.2)` 보더
   - "최근 지정학 이벤트" 헤더 + 이벤트 최대 3건 표시
   - 닫기(X) 버튼 — `useState`로 로컬 dismiss (라운드별 리셋)

2. `frontend/src/components/wargame/FeedPanel.tsx`:
   - `CASCADE_ACTION_TYPES` Set: `military_exercise`, `trade_restriction`, `diplomatic_statement`, `military_movement`
   - 매칭 액션 행에 빨간 좌측 보더(`2px solid #ef4444`) + "연쇄" 뱃지 (9px, red-400 bg)

3. `frontend/src/components/wargame/WarRoom.tsx`:
   - `geopoliticalEvent={streamState.latestGeopoliticalEvent}` → ContextPanel에 전달

### 결과물

| 파일 | 상태 |
|------|------|
| `frontend/src/components/wargame/ContextPanel.tsx` | 수정 |
| `frontend/src/components/wargame/FeedPanel.tsx` | 수정 |
| `frontend/src/components/wargame/WarRoom.tsx` | 수정 (M2에서 이미 수정, 여기서 prop 추가) |

### 성공 기준

- `geopolitical_event` SSE 수신 시 ContextPanel에 빨간 이벤트 배지 표시
- 캐스케이드 액션 타입의 FeedPanel 행에 빨간 보더 + "연쇄" 뱃지
- 배지 닫기 동작 (X 버튼 클릭 시 숨김, 새 이벤트 도착 시 재표시)

---

## 구현 메모

- `trigger_detail`은 `DecisionPointV2` (simulation-stream.ts)에만 정의. `WargameDecisionPointV2` (simulation.ts)에는 없음. WarRoom에서 타입 캐스팅으로 안전 접근.
- `SimulationPanel.tsx`의 `wargamePhaseActive` 조건도 별도 수정 — `isWargameMode && simulating:running` 시 WarRoom 유지 (워게임 중 사이드바/WarRoom 번갈아 나타나는 버그 수정 포함)
- FeedPanel의 캐스케이드 타입 목록은 `engine/events.py`의 `CASCADE_RULES` 키와 일관
