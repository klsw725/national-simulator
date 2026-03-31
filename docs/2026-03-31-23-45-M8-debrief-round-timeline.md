# M8 — DebriefView & RoundTimeline 구현

**일시**: 2026-03-31 23:45
**프롬프트**: M8 — DebriefView (전체 디브리프 오버레이)와 RoundTimeline (하단 타임라인 바) 컴포넌트 구현 및 WarRoom 통합

## 변경 사항

### 신규 파일

1. **`frontend/src/components/wargame/RoundTimeline.tsx`**
   - 수평 타임라인 바 (라운드 마커, 결정 마커 ⚡, 스크러버)
   - Props: `currentRound`, `totalRounds`, `decisionRounds`, `onScrub`, `selectedRound`
   - 현재 라운드 펄스 애니메이션, 클릭으로 라운드 탐색

2. **`frontend/src/components/wargame/DebriefView.tsx`**
   - 시뮬레이션 완료 후 전체화면 디브리프 오버레이
   - Recharts LineChart로 긴장도 곡선 시각화 (결정 라운드에 ReferenceLine)
   - 최종 상태 요약 (총 라운드, 결정 횟수, 최종/최고 긴장도)
   - 결정 히스토리 목록
   - 액션 버튼: 전체 리포트 보기, 새 시뮬레이션, What-If 분기

### 수정 파일

3. **`frontend/src/hooks/useWargame.ts`**
   - `tensionHistory: number[]` — 라운드별 긴장도 추적
   - `decisionHistory: DecisionRecord[]` — 결정 기록 추적
   - `isComplete: boolean` — 시뮬레이션 완료 상태
   - `recordDecision()` — 외부에서 결정 기록 추가
   - SSE `round_complete` → tensionHistory 갱신
   - SSE `decision_resolved` → decisionHistory 갱신
   - SSE `simulation_complete` → isComplete = true
   - mock advancePhase에서도 동일하게 추적

4. **`frontend/src/components/wargame/FeedPanel.tsx`**
   - Props 확장: `totalRounds`, `decisionRounds`, `selectedRound`, `onScrub`
   - 타임라인 플레이스홀더를 실제 RoundTimeline 컴포넌트로 교체

5. **`frontend/src/components/wargame/WarRoom.tsx`**
   - DebriefView 통합 (`wargame.isComplete` 시 렌더)
   - FeedPanel에 타임라인 props 전달
   - `handleDecisionConfirm`에서 `recordDecision` 호출
   - `handleViewReport`, `handleNewSimulation` 핸들러 추가

## 검증

- `tsc --noEmit`: 0 errors
- `npm run build`: 성공
