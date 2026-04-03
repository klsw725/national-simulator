# PRD-3: 프론트엔드 통합 & 레거시 정리

> Phase: 3 / 4
> 예상 기간: 1주
> 선행 조건: PRD-2 완료 (에이전트 엔진 동작, 워게임 루프 완성)
> 참조: v12-spec.md §7 (프론트엔드 통합), §2.4 (삭제 목록)

---

## 목표

프론트엔드를 새 Simulation Service의 SSE 채널에 연결하고, 기존 MiroFish 경로와 레거시 코드를 제거한다.

**이 Phase가 끝나면**: MiroFish 서비스 제거. 프론트엔드가 SSE 단일 채널로 시뮬레이션을 구동. 전체 시스템이 v12 아키텍처로 동작.

---

## M1: SSE 통합 훅 (useSimulationStream)

### 작업

1. `frontend/src/hooks/useSimulationStream.ts` 신규 생성:

```typescript
interface SimulationStreamState {
    phase: string;                      // analyzing | building | simulating | reporting
    status: string;                     // running | paused | completed | failed
    currentRound: number;
    maxRounds: number;
    recentActions: AgentAction[];        // 최근 에이전트 행동
    tensionLevels: Record<string, number>;
    decisionPoint: DecisionPoint | null; // 워게임 개입 지점
    reportId: string | null;
    error: string | null;
}

function useSimulationStream(scenarioId: string): SimulationStreamState
```

2. SSE 이벤트 → 상태 매핑:

| SSE 이벤트 | reducer action | 상태 변화 |
|---|---|---|
| `phase_change` | `PHASE_CHANGE` | phase, status 업데이트 |
| `round_complete` | `ROUND_COMPLETE` | currentRound, tensionLevels 업데이트 |
| `agent_action` | `AGENT_ACTION` | recentActions에 추가 |
| `intervention_required` | `INTERVENTION` | decisionPoint 설정, status = "paused" |
| `report_ready` | `REPORT_READY` | reportId 설정, status = "completed" |
| `error` | `ERROR` | error 설정, status = "failed" |

3. SSE 재연결 로직:
   - EventSource `onerror` → 자동 재연결 (브라우저 기본)
   - `Last-Event-ID` 헤더로 누락 이벤트 catch-up (PRD-0 M4에서 구현한 서버 측 지원)

### 결과물

| 파일 | 상태 |
|---|---|
| `frontend/src/hooks/useSimulationStream.ts` | 신규 |
| `frontend/src/types/simulation-stream.ts` | 신규 (타입 정의) |

### 성공 기준

- 시뮬레이션 실행 시 실시간으로 phase, round, action 업데이트
- SSE 재연결 시 이벤트 유실 없음

---

## M2: WarRoom 연결

### 배경

현재 `useWargame` 훅이 기존 SSE + 폴백 폴링을 사용한다. 이를 `useSimulationStream`으로 교체.

### 작업

1. `frontend/src/components/wargame/WarRoom.tsx` 수정:
   - `useWargame` → `useSimulationStream` 교체
   - 데이터 바인딩 변경: 기존 `wargameState.phase` → `streamState.phase`
   - 결정 제출: 기존 `POST /api/scenario/{id}/wargame/decide` → `POST /api/scenario/{id}/decide_v2`

2. 변경되는 데이터 형태:

| 기존 (useWargame) | 신규 (useSimulationStream) | 변환 |
|---|---|---|
| `phase: "briefing" \| "round" \| ...` | `phase: "analyzing" \| "simulating" \| ...` | phase 이름 매핑 |
| `currentRound` | `currentRound` | 동일 |
| `decisionPoint` | `decisionPoint` | 구조 유사, 옵션 포맷 변경 |
| `isConnected` | SSE 연결 상태 | EventSource.readyState 확인 |

3. 기존 `useWargame`은 제거하지 않고 deprecated 표시 — M6에서 일괄 제거.

### 결과물

| 파일 | 상태 |
|---|---|
| `frontend/src/components/wargame/WarRoom.tsx` | 수정 |

### 성공 기준

- WarRoom이 `useSimulationStream`으로 실시간 업데이트
- 페이즈 전환, 라운드 진행 시각적으로 확인

---

## M3: DecisionOverlay → 외교 행동

### 작업

1. `frontend/src/components/wargame/overlays/DecisionOverlay.tsx` 수정:
   - 기존: 소셜미디어 행동 기반 결정 옵션 (OASIS에서 파생)
   - 신규: 외교/경제/군사 행동 옵션
   - 옵션 카드 디자인은 유지, 내용만 변경

2. 결정 옵션 포맷 변경:

```typescript
// 기존
interface DecisionOption {
    action: string;         // "diplomatic_statement" (소셜미디어에서 매핑됨)
    description: string;
}

// 신규
interface DecisionOption {
    action_type: string;    // "deploy_forces", "propose_negotiation", ...
    target: string;         // "south_china_sea", "china", ...
    intensity: string;      // "low" | "medium" | "high"
    description: string;    // 한국어 설명
    estimated_effect: {     // 예상 효과
        tension_delta: number;
        resource_cost: number;
    };
}
```

3. 결정 제출 API 변경: `POST /api/scenario/{id}/decide_v2`

### 결과물

| 파일 | 상태 |
|---|---|
| `frontend/src/components/wargame/overlays/DecisionOverlay.tsx` | 수정 |
| `frontend/src/types/simulation-stream.ts` | 수정 (DecisionOption 타입) |

### 성공 기준

- 결정 카드에 외교/경제/군사 행동이 표시
- 결정 제출 → 시뮬레이션 resume → 다음 라운드에 반영

---

## M4: LiveActionFeed → 외교 행동 피드

### 작업

1. `frontend/src/components/wargame/LiveActionFeed.tsx` (또는 동등 컴포넌트) 수정:
   - 기존: 소셜미디어 포스트 피드 (에이전트 이름, 포스트 내용, 좋아요 수)
   - 신규: 외교 행동 피드 (국가명, 행동 유형, 대상, 강도, 근거)

2. 행동 피드 항목:

```typescript
interface ActionFeedItem {
    actor: string;          // "미국", "중국", ...
    actorFlag: string;      // 국기 이모지 또는 아이콘
    actionType: string;     // "병력 배치", "협상 제안", ...
    target: string;         // "남중국해", "중국", ...
    intensity: "low" | "medium" | "high";
    reasoning: string;      // "중국의 함대 배치에 대한 억지력 강화"
    round: number;
    timestamp: string;
}
```

3. 데이터 소스: `useSimulationStream`의 `recentActions`

### 결과물

| 파일 | 상태 |
|---|---|
| `frontend/src/components/wargame/LiveActionFeed.tsx` | 수정 |

### 성공 기준

- 에이전트 행동이 실시간으로 피드에 표시
- 행동 유형별 아이콘/색상 구분 (외교=파랑, 경제=녹색, 군사=빨강)

---

## M5: 기타 UI 컴포넌트 조정

### 작업

| 컴포넌트 | 변경 사항 |
|---|---|
| `BriefingOverlay.tsx` | 데이터 소스 변경 (situation_summary), UI 유지 |
| `TensionChart.tsx` | 변경 없음 — tensionLevels 데이터 형태 동일 |
| `PhaseTimeline.tsx` | phase 이름 변경: seed→analyzing, ontology→building, simulation→simulating, report→reporting |
| `DebriefPanel.tsx` | 보고서 데이터 소스 변경 (reportId → `/api/scenario/{id}/report_v2`) |
| `useDataPolling.ts` | **변경 없음** — OSINT 대시보드 독립 유지 |

### 결과물

| 파일 | 상태 |
|---|---|
| `BriefingOverlay.tsx` | 수정 |
| `PhaseTimeline.tsx` | 수정 |
| `DebriefPanel.tsx` | 수정 |

### 성공 기준

- 모든 워게임 UI 컴포넌트가 새 SSE 데이터로 정상 렌더링
- OSINT 대시보드 (useDataPolling) 영향 없음

---

## M6: 레거시 코드 정리

### 배경

Phase 0-2에서 기존 코드와 병행(dual-run)했다. 이제 새 시스템이 동작하므로 레거시를 제거한다.

### 작업

1. **Gateway 측 삭제**:

| 파일 | 삭제 이유 |
|---|---|
| `backend/app/clients/mirofish.py` | MiroFishClient → pg_notify로 대체됨 |
| `backend/app/services/simulation_orchestrator.py` | 수동 상태머신 → LangGraph StateGraph |
| `backend/app/services/event_bus.py` | in-memory Queue → PostgreSQL LISTEN |
| `backend/app/routers/simulation_run.py` | BackgroundTasks 남용 → Simulation Service |
| `backend/app/routers/simulation_live.py` | HTTP 폴링 → SSE |
| `backend/app/routers/simulation_events.py` | 기존 SSE 라우터 → simulation_stream.py |
| `backend/app/geopolitics/mapper.py` | POST→diplomatic_statement 매핑 불필요 |

2. **프론트엔드 측 삭제**:

| 파일 | 삭제 이유 |
|---|---|
| `frontend/src/hooks/useSimulation.ts` | HTTP 폴링 → SSE |
| `frontend/src/hooks/useLiveSimulation.ts` | HTTP 폴링 → SSE |
| `frontend/src/hooks/useWargame.ts` | 기존 SSE+폴백 → useSimulationStream |

3. **main.py 라우터 정리**: 삭제된 라우터 import 제거, simulation_v2 라우터를 정식 경로로 승격:
   - `/api/scenario/{id}/start_v2` → `/api/scenario/{id}/start`
   - `/api/scenario/{id}/decide_v2` → `/api/scenario/{id}/decide`
   - `/api/scenario/{id}/stream` → 유지 (이미 정식 경로)

4. **자신의 변경으로 사용되지 않게 된 import/변수/함수 제거** (AGENTS.md 행동 지침 준수).

### 결과물

| 파일 | 상태 |
|---|---|
| 위 목록의 모든 파일 | 삭제 |
| `backend/app/main.py` | 수정 (삭제된 라우터 제거, v2 라우터 승격) |
| `backend/app/routers/simulation_v2.py` | 이름 변경 → `simulation.py` |

### 성공 기준

- 삭제된 파일에 대한 import 에러 없음
- 기존 기능(워게임 루프, 시나리오 관리)이 새 경로로 정상 동작

---

## M7: MiroFish 서비스 제거

### 작업

1. `docker-compose.yml`에서 mirofish 서비스 정의 제거
2. `external/mirofish-backend/` 디렉토리는 즉시 삭제하지 않고 `.gitignore`에 추가하거나 별도 브랜치로 보관
3. Gateway의 MiroFish 관련 환경 변수 제거 (`MIROFISH_URL`, `MIROFISH_*`)
4. `backend/app/constants.py`에서 MiroFish 관련 상수 제거

### 결과물

| 파일 | 상태 |
|---|---|
| `docker-compose.yml` | 수정 (mirofish 서비스 제거) |
| `.env` | 수정 (MIROFISH_* 변수 제거) |
| `backend/app/constants.py` | 수정 |

### 성공 기준

- `docker compose up` — mirofish 서비스 없이 정상 기동
- 시뮬레이션 전체 플로우가 Simulation Service로만 동작

---

## M8: E2E 통합 검증

### 검증 시나리오

1. **기본 플로우**:
   - 시나리오 생성 (시드 문서 입력)
   - 시뮬레이션 시작 → analyze → build → create_actors → configure → simulating
   - 라운드 진행 → 에이전트 행동 → 긴장도 변화
   - 10라운드 완료 → 보고서 생성
   - 프론트엔드에서 모든 과정 SSE로 실시간 확인

2. **워게임 플로우**:
   - 시뮬레이션 중 긴장도 임계치 초과
   - interrupt → 결정 카드 표시
   - 사용자 결정 선택 (예: 협상 제안)
   - resume → 다음 라운드에 결정 반영
   - 결정이 긴장도에 미치는 영향 확인

3. **체크포인트 복원**:
   - 시뮬레이션 5라운드 진행 중 Simulation Service 재시작
   - 체크포인트에서 복원 → 5라운드부터 계속

4. **OSINT 대시보드 독립성**:
   - 시뮬레이션 실행 중에도 OSINT 대시보드 (useDataPolling) 정상 동작
   - ShadowBroker 데이터 표시에 영향 없음

### 성공 기준 (v12 전체)

- [ ] OSINT 데이터(ShadowBroker)가 온톨로지를 통해 시뮬레이션 컨텍스트로 자동 변환
- [ ] 국가 행위자 에이전트가 외교/경제/군사 행동을 직접 선택 (소셜미디어 매핑 없음)
- [ ] 사용자가 시뮬레이션 중 결정 포인트에서 개입하여 시나리오를 분기 가능
- [ ] 인텔리전스 스타일 보고서 자동 생성
- [ ] 이벤트 전달 지연 < 100ms
- [ ] 라운드 실행 시간 < 30초 (에이전트 병렬 호출)
- [ ] SSE 재연결 시 이벤트 유실 없음
- [ ] MiroFish 서비스 제거 완료
- [ ] HTTP 폴링 기반 서비스 간 통신 0건
- [ ] 프론트엔드 시뮬레이션 관련 HTTP 폴링 훅 0건
