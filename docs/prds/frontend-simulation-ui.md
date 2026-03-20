# PRD: Frontend Simulation UI

> Status: Draft
> Created: 2026-03-20
> Dependencies: PRD 1 (gateway-api-foundation), PRD 5 (result-projection)
> 관련 스펙: `specs/MVP-SPEC.md` Section 2, 4 Phase 3, 7 프론트엔드

---

## 1. 문제 정의

시뮬레이션 결과를 ShadowBroker의 기존 MapLibre 지도 위에 시각화해야 한다. 사용자는 시나리오를 생성하고, 시뮬레이션 진행 상태를 확인하며, 결과를 지도 오버레이와 타임라인 뷰로 탐색할 수 있어야 한다.

핵심 과제:
- ShadowBroker 프론트엔드(Next.js 16 + MapLibre GL 4.7)의 패턴을 따라 확장
- 시뮬레이션 결과 GeoJSON을 MapLibre 레이어로 렌더링
- 시나리오 생성 → 시드 생성 → 시뮬레이션 실행 → 결과 조회 UI 플로우
- 기존 OSINT 레이어와 시뮬레이션 레이어의 공존

## 2. 솔루션 개요

- **시뮬레이션 컨트롤 패널** — 시나리오 생성 폼 + 파이프라인 진행 상태 UI
- **MapLibre 시뮬레이션 레이어** — 행위자 Point + 관계 LineString + 긴장 히트맵
- **시뮬레이션 타임라인** — 라운드별 에이전트 행동 타임라인
- **예측 보고서 뷰어** — MiroFish 보고서 마크다운 렌더링

## 3. 기술 상세

### 3.1 ShadowBroker 프론트엔드 아키텍처 (검증 완료)

| 항목 | 값 |
|------|------|
| 프레임워크 | Next.js 16.1.6 (App Router) |
| UI | React 19.2.3 + Tailwind CSS 4 |
| 지도 | MapLibre GL 4.7.1 + react-map-gl 8.1.0 |
| 상태관리 | React Context (DashboardDataContext) |
| 데이터 폴링 | useDataPolling 훅 (fast 15s, slow 120s) |
| 소스 업데이트 | useImperativeSource 훅 (명령형, React 렌더링 우회) |
| 테마 | Dark/Light (CSS Variables + Carto basemaps) |

### 3.2 ShadowBroker 레이어 추가 패턴

SB 프론트엔드는 5단계 패턴으로 데이터 레이어를 추가한다:

```
1. GeoJSON 빌더 함수 (geoJSONBuilders.ts)
   → 데이터 배열을 GeoJSON FeatureCollection으로 변환

2. 타입 정의 (types/dashboard.ts)
   → 데이터 인터페이스 추가

3. DashboardData 인터페이스 확장
   → 새 필드 추가

4. 레이어 토글 (page.tsx의 activeLayers)
   → 레이어 on/off 상태 추가

5. Source + Layer 등록 (MaplibreViewer.tsx)
   → useImperativeSource + <Source> + <Layer> JSX
```

### 3.3 프론트엔드 프로젝트 구조

```
frontend/
├── src/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx                    # 메인 대시보드
│   │   └── api/[...path]/route.ts      # Gateway API 프록시
│   ├── components/
│   │   ├── simulation/
│   │   │   ├── SimulationPanel.tsx      # 시뮬레이션 컨트롤 패널
│   │   │   ├── ScenarioForm.tsx         # 시나리오 생성 폼
│   │   │   ├── PipelineProgress.tsx     # 파이프라인 진행 상태
│   │   │   ├── SimulationTimeline.tsx   # 라운드별 타임라인
│   │   │   └── ReportViewer.tsx         # 보고서 뷰어
│   │   └── map/
│   │       └── geoJSONBuilders.ts       # + 시뮬레이션 GeoJSON 빌더
│   ├── hooks/
│   │   └── useSimulation.ts             # 시뮬레이션 상태 관리 훅
│   ├── types/
│   │   └── simulation.ts               # 시뮬레이션 타입 정의
│   └── lib/
│       └── gatewayApi.ts               # Gateway API 클라이언트
├── package.json
├── next.config.ts
└── Dockerfile
```

### 3.4 주요 컴포넌트

#### SimulationPanel (사이드 패널)

```tsx
interface SimulationPanelProps {
  isOpen: boolean;
  onClose: () => void;
  onScenarioCreated: (scenarioId: string) => void;
}

// 탭 구조:
// [시나리오 생성] → ScenarioForm
// [진행 상태] → PipelineProgress
// [결과] → SimulationTimeline + ReportViewer
```

#### ScenarioForm

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

#### PipelineProgress

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

### 3.5 MapLibre 시뮬레이션 레이어

#### Actor Points (행위자 위치)

```tsx
// geoJSONBuilders.ts에 추가
export function buildSimulationActorsGeoJSON(geojson?: GeoJSON.FeatureCollection): GeoJSON.FeatureCollection {
  // feature_type === "actor"인 피처만 필터링
  // 이미 GeoJSON이므로 그대로 반환 (필터링만)
}

// MaplibreViewer.tsx에 추가
<Source id="simulation-actors" type="geojson" data={actorsGeoJSON}>
  <Layer
    id="simulation-actors-layer"
    type="circle"
    paint={{
      'circle-radius': ['interpolate', ['linear'], ['get', 'tension_level'],
        0, 8,
        0.5, 14,
        1, 22
      ],
      'circle-color': ['get', 'color'],
      'circle-opacity': 0.8,
      'circle-stroke-width': 2,
      'circle-stroke-color': '#ffffff'
    }}
  />
  <Layer
    id="simulation-actors-label"
    type="symbol"
    layout={{
      'text-field': ['get', 'actor'],
      'text-size': 12,
      'text-offset': [0, 2],
      'text-anchor': 'top'
    }}
    paint={{
      'text-color': '#ffffff',
      'text-halo-color': '#000000',
      'text-halo-width': 1
    }}
  />
</Source>
```

#### Relationship Lines (관계 라인)

```tsx
export function buildSimulationRelationsGeoJSON(geojson?: GeoJSON.FeatureCollection): GeoJSON.FeatureCollection {
  // feature_type === "relationship"인 피처만 필터링
}

<Source id="simulation-relations" type="geojson" data={relationsGeoJSON}>
  <Layer
    id="simulation-relations-layer"
    type="line"
    paint={{
      'line-color': ['get', 'color'],
      'line-width': ['interpolate', ['linear'], ['get', 'strength'],
        0, 1,
        0.5, 2,
        1, 4
      ],
      'line-opacity': 0.6,
      'line-dasharray': ['case',
        ['==', ['get', 'relationship_type'], 'hostile'], ['literal', [2, 2]],
        ['literal', [1]]
      ]
    }}
  />
</Source>
```

### 3.6 Gateway API 클라이언트

```typescript
// lib/gatewayApi.ts
const GATEWAY_URL = process.env.NEXT_PUBLIC_GATEWAY_URL || '';

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

  getResults: (scenarioId: string) =>
    fetch(`${GATEWAY_URL}/api/scenario/${scenarioId}/results`),

  getGeoJSON: (scenarioId: string) =>
    fetch(`${GATEWAY_URL}/api/scenario/${scenarioId}/geojson`),

  getReport: (scenarioId: string) =>
    fetch(`${GATEWAY_URL}/api/scenario/${scenarioId}/report`),
};
```

### 3.7 프론트엔드 접근 방식

ShadowBroker 프론트엔드를 직접 수정하지 않고, **별도 프론트엔드 프로젝트**로 구축한다 (MVP-SPEC.md 설계 원칙 #1, AGENTS.md "소스 프로젝트는 절대 수정하지 않는다").

두 가지 접근:
1. **독립 프론트엔드** — SB의 MapLibre 패턴을 참조하되 별도 Next.js 앱 (port 3000). Gateway API를 통해 SB 데이터도 조회.
2. **SB 프론트엔드 포크** — SB 프론트엔드 코드를 osint-simulator/frontend/로 복사하여 확장.

> MVP에서는 **접근 1 (독립 프론트엔드)**을 권장. SB 프론트엔드의 MapLibre 설정, 스타일, 유틸리티를 참조하되 자체 앱으로 구축. OSINT 데이터는 Gateway 프록시(`/api/osint/*`)를 통해 조회.

## 4. 마일스톤

- [ ] **M1: 프론트엔드 프로젝트 셋업** — Next.js 16 + React 19 + Tailwind CSS + MapLibre GL + react-map-gl 프로젝트 초기화. SB의 mapStyles.ts, useImperativeSource 패턴 참조. Gateway API 프록시 라우트 설정.
  - 검증: `npm run dev` → MapLibre 지도 렌더링 + Gateway API 연결

- [ ] **M2: 기본 OSINT 지도 레이어** — Gateway OSINT 프록시를 통해 SB 데이터 폴링. 선박 + 항공기 레이어 렌더링 (SB 패턴 동일). 레이어 토글 UI.
  - 검증: 지도에 실시간 선박/항공기 표시. SB와 동일한 시각적 결과

- [ ] **M3: 시나리오 생성 폼** — SimulationPanel 사이드 패널. ScenarioForm (이름, 해역 bbox, 질문, 라운드 수). 해역은 지도에서 드래그로 선택 가능. Gateway API 호출하여 시나리오 생성.
  - 검증: 폼 입력 → POST /api/scenario → 시나리오 생성 성공

- [ ] **M4: 파이프라인 진행 상태 UI** — PipelineProgress 컴포넌트 (6단계 스텝 표시). GET /api/scenario/{id}/status 5초 폴링. 현재 단계 하이라이트 + 완료 단계 체크마크. 에러 상태 표시.
  - 검증: 시뮬레이션 시작 → 진행 상태 실시간 업데이트 표시

- [ ] **M5: 시뮬레이션 결과 MapLibre 오버레이** — 완료된 시뮬레이션의 GeoJSON을 MapLibre 레이어로 렌더링. 행위자 Point (circle + label) + 관계 LineString. 행위자 클릭 시 팝업 (입장, 핵심 발언, 긴장 수준).
  - 검증: 시뮬레이션 완료 → 지도에 행위자 원형 마커 + 관계 라인 표시

- [ ] **M6: 시뮬레이션 타임라인 뷰어** — SimulationTimeline 컴포넌트. 라운드별 에이전트 행동 목록 (포스트, 리포스트, 인용). 라운드 슬라이더로 시간 탐색. 에이전트별 필터링.
  - 검증: 라운드 슬라이더 조작 → 해당 라운드의 행동 목록 표시

- [ ] **M7: 보고서 뷰어 + 시나리오 목록** — ReportViewer (마크다운 렌더링). 시나리오 목록 패널 (생성된 시나리오 조회/삭제). 시나리오 선택 → 결과 로드.
  - 검증: 보고서 마크다운 렌더링. 시나리오 목록에서 선택 → 결과 표시

- [ ] **M8: E2E 데모** — 남중국해 시나리오 전체 플로우: 시나리오 생성 → 시드 생성 → 시뮬레이션 실행 → 지도 오버레이 + 타임라인 + 보고서. 사용자 개입 없이 자동 진행.
  - 검증: UI에서 시나리오 생성 후 결과까지 전체 플로우 완주

## 5. 성공 기준

- 지도에 실시간 OSINT 데이터와 시뮬레이션 결과가 동시에 표시된다
- 시나리오 생성 → 시뮬레이션 완료까지 진행 상태를 실시간으로 확인할 수 있다
- 시뮬레이션 결과가 행위자 마커 + 관계 라인으로 지도에 오버레이된다
- 타임라인으로 라운드별 에이전트 행동을 탐색할 수 있다
- 예측 보고서를 읽을 수 있다
- 남중국해 시나리오 E2E 데모가 동작한다

## 6. 위험 및 완화

| 위험 | 완화 |
|------|------|
| SB 프론트엔드 패턴과의 불일치 | SB 코드를 직접 참조하여 동일 패턴 적용. react-map-gl + useImperativeSource 훅 재사용 |
| MapLibre 성능 (많은 레이어) | 시뮬레이션 레이어는 feature 수가 적음 (국가 수십 개). 성능 문제 없을 것으로 예상 |
| 파이프라인 실행 시간이 길어 UX 문제 | PipelineProgress에 예상 소요 시간 표시. 백그라운드 실행 후 알림 |
| Gateway API CORS 문제 | Gateway에 CORS 설정 추가 (PRD 1). 프론트엔드 API 프록시 라우트 활용 |

## 7. 참고

### 관련 PRD
- **PRD 1 (gateway-api-foundation)** — Gateway API 엔드포인트
- **PRD 2 (shadowbroker-integration)** — OSINT 프록시 데이터
- **PRD 5 (result-projection)** — GeoJSON 데이터 구조

### ShadowBroker 프론트엔드 참조
- 지도 컴포넌트: `/home/swlee/Shadowbroker/frontend/src/components/MaplibreViewer.tsx`
- GeoJSON 빌더: `/home/swlee/Shadowbroker/frontend/src/components/map/geoJSONBuilders.ts`
- 명령형 소스: `/home/swlee/Shadowbroker/frontend/src/components/map/hooks/useImperativeSource.ts`
- 데이터 폴링: `/home/swlee/Shadowbroker/frontend/src/hooks/useDataPolling.ts`
- 타입 정의: `/home/swlee/Shadowbroker/frontend/src/types/dashboard.ts`
- 패키지: `/home/swlee/Shadowbroker/frontend/package.json`

> **주의**: ShadowBroker 프론트엔드 소스 코드를 직접 수정하지 않는다 (AGENTS.md). 패턴만 참조.

## 진행 로그

| 날짜 | 상태 | 내용 |
|------|------|------|
| 2026-03-20 | Draft | PRD 초안 작성 |
