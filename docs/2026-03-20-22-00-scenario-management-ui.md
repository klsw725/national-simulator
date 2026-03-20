# PRD 6b: Scenario Management UI 구현

> 날짜: 2026-03-20
> 프롬프트: `prd-next` → PRD 6b (scenario-management-ui) 선택 → 구현

## 변경 사항

### 신규 파일 (7개)

| 파일 | 설명 |
|------|------|
| `src/types/simulation.ts` | Scenario, ScenarioFormData, PipelineStep, PipelineStatus 인터페이스 |
| `src/lib/gatewayApi.ts` | 확장 — 시나리오 CRUD, 시드 생성, 시뮬레이션 시작/상태/결과/GeoJSON/보고서 API |
| `src/hooks/useSimulation.ts` | createAndRun (시나리오→시드→시뮬레이션), 5s 상태 폴링, 시나리오 CRUD |
| `src/components/simulation/SimulationPanel.tsx` | 400px 우측 패널, 3탭 (생성/진행/목록) |
| `src/components/simulation/ScenarioForm.tsx` | 시나리오 생성 폼 — 이름, 해역 프리셋 4개, 질문, 라운드 슬라이더 |
| `src/components/simulation/PipelineProgress.tsx` | 6단계 파이프라인 진행 상태 (lucide 아이콘) |
| `src/components/simulation/ScenarioList.tsx` | 시나리오 목록 + 삭제 + 선택 |

### 수정 파일 (2개)

| 파일 | 변경 |
|------|------|
| `src/app/page.tsx` | SimulationPanel + 플로팅 토글 버튼 추가 |
| `src/app/globals.css` | spin 키프레임 애니메이션 추가 |

## 검증

- ✅ `npm run build` — TypeScript 에러 0, 빌드 성공
