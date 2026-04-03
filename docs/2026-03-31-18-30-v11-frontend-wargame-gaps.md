# v11 프론트엔드 워게임 갭 구현

## 프롬프트

```
TASK: Implement the frontend-side v11 wargame gaps in the current repo.
EXPECTED OUTCOME: Make concrete code changes for frontend/src so v11 is closer to spec-complete:
useWargame hydration/SSE handling, API glue, WarRoom routing/debrief continuity,
and key UI behavior gaps for overlays/timeline/debrief.
```

## 변경 파일

| 파일 | 변경 유형 | 내용 |
|------|----------|------|
| `frontend/src/lib/api/wargameApi.ts` | 신규 | 워게임 전용 API 모듈 (status, decision resolve, resume) |
| `frontend/src/lib/gatewayApi.ts` | 수정 | wargameApi re-export 추가 |
| `frontend/src/hooks/useWargame.ts` | 수정 | SSE stale closure 수정, 초기 hydration, polling tension 추적, round_complete/simulation_complete 데이터 반영 |
| `frontend/src/components/wargame/WarRoom.tsx` | 수정 | raw fetch → wargameApi 사용, 결정 후 resumeWargame 호출, onViewReport/onCreateWhatIf 콜백 연결 |
| `frontend/src/components/simulation/SimulationPanel.tsx` | 수정 | useLiveSimulation으로 워게임 중 실시간 액션 폴링, WarRoom에 live actions 전달 |
| `frontend/src/components/wargame/FeedPanel.tsx` | 수정 | selectedRound로 액션 필터링, 라운드 필터 표시기 + 전체보기 버튼 |

## 수정 상세

### 1. wargameApi.ts (신규)

- `getWargameStatus(scenarioId)` — `/api/scenario/{id}/wargame_status` GET
- `resolveWargameDecision(scenarioId, dpId, optionId)` — 기존 decision_points resolve 엔드포인트 래핑
- `resumeWargame(scenarioId)` — `/api/scenario/{id}/continue` POST (결정 후 백엔드에 재개 신호)

### 2. useWargame.ts 버그 수정

- **Stale closure 수정**: `handleSSEEvent`의 `round_complete` 핸들러가 `state.tension`을 직접 참조하던 것을 `prev.tension` (functional updater) 패턴으로 변경
- **초기 hydration 추가**: SSE 연결 시 `hydrateFromBackend()` 호출하여 백엔드에서 현재 상태를 가져옴. 페이지 새로고침 시 상태 복원 가능
- **Polling tension 추적**: 폴링 fallback에서 상태 업데이트 시 `tensionHistory`에도 새 tension 값 추가
- **`simulation_complete` 데이터 반영**: 이벤트의 `final_tension`, `total_rounds` 값을 상태에 반영
- **`decision_required` fallback**: briefing/decision_point 데이터가 없으면 `hydrateFromBackend()`로 전체 상태 재조회
- **`phase_change` round 반영**: 이벤트의 `round` 값도 상태에 반영

### 3. WarRoom.tsx 결정 흐름 개선

- raw `fetch` → `resolveWargameDecision` + `resumeWargame` API 함수 사용
- 결정 확정 후 `resumeWargame(scenarioId)` 호출하여 백엔드에 다음 라운드 진행 신호 전송
- `onViewReport`, `onCreateWhatIf` props 추가하여 SimulationPanel에서 콜백 연결
- `handleScrub` 함수로 round=0일 때 필터 해제 처리

### 4. SimulationPanel.tsx 라이브 액션 연결

- `useLiveSimulation` 훅 추가: 워게임 모드일 때 `simulating:running` 상태로 매핑하여 액션 폴링 활성화
- WarRoom에 `live.actions` 전달 (기존 `actions={[]}` 제거)
- `onViewReport` → report 탭 전환, `onCreateWhatIf` → whatif 비교 모달 연결

### 5. FeedPanel.tsx 라운드 필터링

- `selectedRound !== null`일 때 해당 라운드 액션만 표시
- 필터 활성 시 "· R{n}" 라벨 + "전체 보기" 버튼 표시
- 필터 비활성 시 기존 "최신으로 ↓" 버튼 유지

## 검증

- `npx tsc --noEmit`: 0 errors (전체 프로젝트)

## 남은 블로커 (백엔드/외부 의존)

| 블로커 | 의존 레이어 | 설명 |
|--------|-----------|------|
| SSE 엔드포인트 미구현 | backend | `/api/scenario/{id}/events` SSE 스트림이 아직 없음. 프론트엔드는 SSE 실패 시 polling fallback으로 동작 |
| wargame_status 엔드포인트 미구현 | backend | `/api/scenario/{id}/wargame_status` GET이 아직 없음. hydration/polling이 실패하면 mock 모드로 fallback |
| 워게임 파이프라인 상태 문자열 미확정 | backend | `simulating:wargame`, `wargame:paused:round_N` 등 정확한 상태 문자열이 백엔드에서 확정되어야 SimulationPanel의 wargame 감지 로직이 동작 |
| 렌즈별 맵 오버레이 | frontend/map | LensPanel의 렌즈 선택이 맵 오버레이에 반영되지 않음. MaplibreViewer에 렌즈 연동 필요 |
| What-If 분기 생성 | backend | DebriefView/DecisionCard의 "What-If 분기" 버튼이 기존 WhatIfEngine을 호출해야 하나, 워게임 컨텍스트에서의 분기 생성 API가 미확정 |
| 디브리프 → 리포트 연결 | frontend | "전체 리포트 보기" 버튼이 SimulationPanel의 report 탭으로 전환하나, 워게임 모드에서는 WarRoom이 전체 화면을 차지하므로 UX 전환 방식 결정 필요 |
