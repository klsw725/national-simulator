# PRD: Scenario Management UI

> Status: Draft
> Created: 2026-03-20
> Dependencies: PRD 1 (gateway-api-foundation), PRD 6a (frontend-foundation)
> 관련 스펙: `specs/MVP-SPEC.md` Section 4 Phase 1-2

---

## 1. 문제 정의

사용자가 시뮬레이션 시나리오를 생성하고, 파이프라인 진행 상태를 확인하며, 과거 시나리오를 관리할 수 있는 UI가 필요하다. 시나리오 생성 폼(해역 선택, 질문 입력), 6단계 파이프라인 진행 상태 표시, 시나리오 목록/삭제 기능을 구현한다.

## 2. 솔루션 개요

- **SimulationPanel** — 사이드 패널 (시나리오 생성 + 진행 상태 + 시나리오 목록)
- **ScenarioForm** — 해역 bbox 선택 + 질문 입력 + 라운드 수 설정
- **PipelineProgress** — 6단계 파이프라인 진행 상태 실시간 표시
- **시나리오 목록** — 생성된 시나리오 조회/선택/삭제

## 3. 기술 상세

### 3.1 컴포넌트 구조

```
frontend/src/components/simulation/
├── SimulationPanel.tsx      # 시뮬레이션 컨트롤 패널 (사이드)
├── ScenarioForm.tsx         # 시나리오 생성 폼
├── PipelineProgress.tsx     # 파이프라인 진행 상태
└── ScenarioList.tsx         # 시나리오 목록

frontend/src/hooks/
└── useSimulation.ts         # 시뮬레이션 상태 관리 훅
```

### 3.2 SimulationPanel

```tsx
interface SimulationPanelProps {
  isOpen: boolean;
  onClose: () => void;
  onScenarioCreated: (scenarioId: string) => void;
}

// 탭 구조:
// [시나리오 생성] → ScenarioForm
// [진행 상태] → PipelineProgress
// [시나리오 목록] → ScenarioList
```

### 3.3 ScenarioForm

```tsx
interface ScenarioFormData {
  name: string;
  region: {
    bbox: [number, number, number, number]; // 지도에서 드래그로 선택
    name: string;
  };
  question: string;
  max_rounds: number;        // 기본값 10, 범위 1-30
  data_sources: string[];    // ["ships", "geopolitics"]
}
```

해역 bbox는 지도에서 드래그로 선택 가능. MapLibre의 draw interaction 또는 간단한 드래그 박스 구현.

### 3.4 PipelineProgress

```tsx
// 6단계 파이프라인 진행 상태 표시
const PIPELINE_STEPS = [
  { id: 'seed', label: '시드 문서 생성', icon: 'FileText' },
  { id: 'ontology', label: '온톨로지 생성', icon: 'Network' },
  { id: 'graph', label: '그래프 빌드', icon: 'GitBranch' },
  { id: 'prepare', label: '시뮬레이션 준비', icon: 'Settings' },
  { id: 'running', label: '시뮬레이션 실행', icon: 'Play' },
  { id: 'report', label: '보고서 생성', icon: 'FileCheck' },
];

// 상태 폴링: GET /api/scenario/{id}/status (5초 간격)
```

### 3.5 Gateway API 클라이언트 (시나리오 관리 부분)

```typescript
// lib/gatewayApi.ts에 추가
export const gatewayApi = {
  // 시나리오
  createScenario: (data: ScenarioFormData) =>
    fetch(`${GATEWAY_URL}/api/scenario`, { method: 'POST', body: JSON.stringify(data) }),

  getScenarios: () =>
    fetch(`${GATEWAY_URL}/api/scenario`),

  getScenario: (id: string) =>
    fetch(`${GATEWAY_URL}/api/scenario/${id}`),

  deleteScenario: (id: string) =>
    fetch(`${GATEWAY_URL}/api/scenario/${id}`, { method: 'DELETE' }),

  // 시드
  generateSeed: (scenarioId: string) =>
    fetch(`${GATEWAY_URL}/api/scenario/${scenarioId}/seed`, { method: 'POST' }),

  getSeed: (scenarioId: string) =>
    fetch(`${GATEWAY_URL}/api/scenario/${scenarioId}/seed`),

  // 시뮬레이션
  startSimulation: (scenarioId: string) =>
    fetch(`${GATEWAY_URL}/api/scenario/${scenarioId}/simulate`, { method: 'POST' }),

  getStatus: (scenarioId: string) =>
    fetch(`${GATEWAY_URL}/api/scenario/${scenarioId}/status`),
};
```

### 3.6 시뮬레이션 타입 정의

```typescript
// types/simulation.ts
interface Scenario {
  id: string;
  name: string;
  region_bbox: [number, number, number, number];
  region_name: string;
  question: string;
  max_rounds: number;
  data_sources: string[];
  status: 'created' | 'seeding' | 'simulating' | 'completed' | 'failed';
  created_at: string;
  updated_at: string;
}

interface PipelineStatus {
  scenario_id: string;
  current_step: string;
  progress_percent: number;
  steps: {
    id: string;
    status: 'pending' | 'running' | 'completed' | 'failed';
    message?: string;
  }[];
}
```

## 4. 마일스톤

- [x] **M1: SimulationPanel + ScenarioForm** — 사이드 패널 컴포넌트. 시나리오 생성 폼 (이름, 해역 bbox, 질문, 라운드 수). 해역은 지도에서 드래그로 선택 가능. Gateway API 호출하여 시나리오 생성.
  - 검증: 폼 입력 → POST /api/scenario → 시나리오 생성 성공

- [x] **M2: PipelineProgress + 상태 폴링** — PipelineProgress 컴포넌트 (6단계 스텝 표시). GET /api/scenario/{id}/status 5초 폴링. 현재 단계 하이라이트 + 완료 단계 체크마크. 에러 상태 표시.
  - 검증: 시뮬레이션 시작 → 진행 상태 실시간 업데이트 표시

- [x] **M3: 시나리오 목록 + 관리** — ScenarioList 컴포넌트. 생성된 시나리오 목록 조회. 시나리오 선택 → 상세/결과 로드. 시나리오 삭제.
  - 검증: 시나리오 목록 표시 + 선택 + 삭제 동작

## 5. 성공 기준

- 시나리오 생성 폼에서 해역을 지도 위에서 선택할 수 있다
- 시나리오 생성 → 시뮬레이션 시작까지 UI 플로우가 동작한다
- 파이프라인 6단계 진행 상태가 실시간으로 표시된다
- 시나리오 목록에서 과거 시나리오를 조회/선택/삭제할 수 있다

## 6. 위험 및 완화

| 위험 | 완화 |
|------|------|
| 파이프라인 실행 시간이 길어 UX 문제 | PipelineProgress에 예상 소요 시간 표시. 백그라운드 실행 후 알림 |
| bbox 드래그 선택 UX가 복잡 | 간단한 드래그 박스로 시작. 프리셋 해역(남중국해, 대만해협 등) 버튼 제공 |

## 7. 참고

### 관련 PRD
- **PRD 1 (gateway-api-foundation)** — Gateway API 엔드포인트 (시나리오 CRUD)
- **PRD 6a (frontend-foundation)** — 프론트엔드 프로젝트 기반 + 지도
- **PRD 6c (simulation-visualization)** — 시뮬레이션 결과 시각화 (이 PRD의 후속)

## 진행 로그

| 날짜 | 상태 | 내용 |
|------|------|------|
| 2026-03-20 | Draft | PRD 6 분할로 생성 |
