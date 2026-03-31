# M6 — War Room (Situation Room) 기본 레이아웃

> 날짜: 2026-03-31
> PRD: docs/specs/v11-wargame-loop/prds/v11-frontend-war-room.md

## 프롬프트

M6 — War Room (Situation Room) base layout 구현. `wargame_enabled=true` 시 탭 기반 SimulationPanel 대신 페이즈 기반 상황실 UI 렌더링.

## 변경 요약

### 신규 파일

| 파일 | 역할 |
|------|------|
| `frontend/src/hooks/useWargame.ts` | SSE 연결 + 폴링 폴백 + mock 데이터. WargameState 관리 (phase, round, tension, actorStates, lens) |
| `frontend/src/components/wargame/WarRoom.tsx` | 상황실 메인 레이아웃. pointer-events 투명 오버레이로 기존 MaplibreViewer 위에 패널 배치 |
| `frontend/src/components/wargame/PhaseBar.tsx` | 상단 바: 4 페이즈 인디케이터 + 라운드 카운터 + 역할 배지 + 긴장도 게이지 |
| `frontend/src/components/wargame/LensPanel.tsx` | 좌측 사이드바 (56px): 6개 렌즈 버튼 (정보전/외교/군사/경제/관계/What-If) |
| `frontend/src/components/wargame/ContextPanel.tsx` | 우측 패널 (320px): 행위자 상태 요약 (위협/압력/자원 바) |
| `frontend/src/components/wargame/FeedPanel.tsx` | 하단 패널 (200px): 소셜 미디어 피드 (70%) + 타임라인 placeholder (30%) |

### 수정 파일

| 파일 | 변경 |
|------|------|
| `frontend/src/types/simulation.ts` | `WargamePhase`, `WargameState`, `ActorState`, `RoundBriefing`, `WargameLens` 타입 추가. `SimulationParams`/`SimulationParamsInput`에 `wargame_enabled?` 추가 |
| `frontend/src/components/simulation/SimulationPanel.tsx` | `WarRoom` import + `wargame_enabled=true` 시 WarRoom 렌더링 분기 |

## 레이아웃 구조

```
┌──────────────────────────────────────────────────────────┐
│ PhaseBar (full width, 48px)                               │
├──────┬──────────────────────────────────┬────────────────┤
│ Lens │ MAP (투명 — 기존 MaplibreViewer)  │ ContextPanel   │
│(56px)│                                  │ (320px)        │
├──────┴──────────────────────────────────┴────────────────┤
│ FeedPanel (200px) — 피드 70% + 타임라인 30%               │
└──────────────────────────────────────────────────────────┘
```

## 검증

- `npm run build` — 성공 (TypeScript 오류 없음)
- `npx tsc --noEmit` — 성공
- 기존 `wargame_enabled=false` 시뮬레이션 패널 동작 변경 없음
