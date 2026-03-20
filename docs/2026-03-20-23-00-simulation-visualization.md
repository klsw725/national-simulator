# PRD 6c: Simulation Visualization

**일시**: 2026-03-20 23:00
**프롬프트**: Create Simulation Visualization (PRD 6c — FINAL MVP PRD)

## 변경 요약

시뮬레이션 완료 후 결과를 MapLibre 지도 오버레이와 사이드 패널에서 시각화하는 기능 구현.

## 변경 파일

### 수정
- `frontend/src/components/map/geoJSONBuilders.ts` — `buildSimulationActorsGeoJSON`, `buildSimulationRelationsGeoJSON` 추가
- `frontend/src/components/map/MaplibreViewer.tsx` — 시뮬레이션 레이어(actors/relations/labels) + 클릭 팝업 추가
- `frontend/src/hooks/useSimulation.ts` — `simulationGeoJSON`, `simulationResults`, `reportMarkdown` 상태 + `loadResults` 함수 추가. 완료 시 자동 fetch.
- `frontend/src/components/simulation/SimulationPanel.tsx` — `useSimulation`을 외부 prop으로 받도록 변경, 타임라인/리포트 탭 추가
- `frontend/src/app/page.tsx` — `useSimulation`을 page 레벨로 리프트, MaplibreViewer와 SimulationPanel에 상태 전달
- `frontend/src/types/simulation.ts` — `SimulationAction` 타입 추가

### 신규 생성
- `frontend/src/components/simulation/SimulationTimeline.tsx` — 라운드별 에이전트 액션 타임라인 (슬라이더 + 액션 리스트)
- `frontend/src/components/simulation/ReportViewer.tsx` — 마크다운 리포트 렌더러 (regex 기반, 외부 의존성 없음)

## 아키텍처 결정

- `useSimulation` 훅을 `page.tsx`로 리프트하여 MaplibreViewer와 SimulationPanel 양쪽에 상태 공유
- 마크다운 렌더링은 `react-markdown` 없이 간단한 regex 파서로 구현 (h1-h3, bold, italic, inline code, list, paragraph)
- 시뮬레이션 완료 시 geojson/results/report를 `Promise.allSettled`로 병렬 fetch (부분 실패 허용)
- MapLibre 레이어: relations(line) → actors(circle) → labels(symbol) 순서로 렌더링

## 검증
- `npm run build` 통과 (TypeScript 에러 0)
