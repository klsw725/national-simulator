# v11 맵/렌즈/컨텍스트 연동 보강

- 날짜: 2026-03-31 13:33 UTC
- 사용자 프롬프트: `2`

## 목적

워게임 상황실의 남은 프론트엔드 갭 중 렌즈 버튼 무반응, 맵 phase 반응 부족, 컨텍스트 패널 정적 문제를 줄이기 위해 페이지-패널-맵 경계를 연결했다.

## 주요 변경

### 렌즈 → 맵 레이어 연동

- `frontend/src/app/page.tsx`
  - 렌즈별 레이어 preset 적용
  - `wargameOverlay` 상태 추가
  - 워게임 중에는 LensPanel이 레이어 가시성 override를 제어
- `frontend/src/components/simulation/SimulationPanel.tsx`
  - `onWargameOverlay` prop 전달
- `frontend/src/components/wargame/WarRoom.tsx`
  - active lens / phase를 상위로 전달

### phase-aware map styling

- `frontend/src/components/map/MaplibreViewer.tsx`
  - `wargamePhase` prop 기반으로 simulation actor / relation 시각 강조

### 컨텍스트 패널 상호작용

- `frontend/src/components/wargame/FeedPanel.tsx`
  - 피드 액션 클릭 시 선택된 엔티티 emit
- `frontend/src/components/wargame/ContextPanel.tsx`
  - 선택된 엔티티 상세 카드 표시/닫기
- `frontend/src/components/wargame/WarRoom.tsx`
  - selected entity 상태 연결

### 타임라인/표시 보강

- `frontend/src/hooks/useWargame.ts`
  - 라운드 snapshot 조회 사용 유지
- `frontend/src/components/wargame/WarRoom.tsx`
  - 스크럽된 라운드 snapshot을 PhaseBar/ContextPanel에 반영

## 검증

- `npx tsc --noEmit` 성공
- `npm run build` 성공

## 비고

- 렌즈는 현재 안전한 preset 기반 레이어 가시성 override 방식이다.
- 지도 자체의 완전한 객체 선택/행동 연동까지는 추가 확장 여지가 있다.
