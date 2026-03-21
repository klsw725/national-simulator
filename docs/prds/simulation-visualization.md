# PRD: Simulation Visualization

> Status: Draft
> Created: 2026-03-20
> Dependencies: PRD 5 (result-projection), PRD 6a (frontend-foundation), PRD 6b (scenario-management-ui)
> 관련 스펙: `specs/MVP-SPEC.md` Section 4 Phase 3, 5.5

---

## 1. 문제 정의

시뮬레이션이 완료되면 결과를 지도 오버레이, 라운드별 타임라인, 예측 보고서로 시각화해야 한다. PRD 5(result-projection)에서 생성된 GeoJSON을 MapLibre 레이어로 렌더링하고, MiroFish 시뮬레이션의 라운드별 에이전트 행동을 탐색할 수 있는 타임라인 뷰와 보고서 뷰어를 구현한다.

## 2. 솔루션 개요

- **MapLibre 시뮬레이션 레이어** — 행위자 Point + 관계 LineString + 팝업
- **SimulationTimeline** — 라운드별 에이전트 행동 타임라인
- **ReportViewer** — MiroFish 보고서 마크다운 렌더링
- **시뮬레이션 레이어 토글** — 기존 OSINT 레이어와 시뮬레이션 레이어 공존

## 3. 기술 상세

### 3.1 MapLibre 시뮬레이션 레이어

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

### 3.2 컴포넌트 구조

```
frontend/src/components/simulation/
├── SimulationTimeline.tsx   # 라운드별 타임라인
└── ReportViewer.tsx         # 보고서 뷰어
```

### 3.3 SimulationTimeline

```tsx
interface SimulationTimelineProps {
  scenarioId: string;
  results: SimulationResults;
}

// 기능:
// - 라운드 슬라이더로 시간 탐색
// - 라운드별 에이전트 행동 목록 (포스트, 리포스트, 인용)
// - 에이전트별 필터링
// - 행동 유형별 아이콘 (CREATE_POST, QUOTE_POST, REPOST, LIKE, FOLLOW, DO_NOTHING)
```

### 3.4 ReportViewer

```tsx
interface ReportViewerProps {
  scenarioId: string;
  reportMarkdown: string;
}

// MiroFish 보고서 마크다운을 렌더링
// react-markdown 또는 유사 라이브러리 사용
```

### 3.5 Gateway API 클라이언트 (결과 조회 부분)

```typescript
// lib/gatewayApi.ts에 추가
export const gatewayApi = {
  // 결과
  getResults: (scenarioId: string) =>
    fetch(`${GATEWAY_URL}/api/scenario/${scenarioId}/results`),

  getGeoJSON: (scenarioId: string) =>
    fetch(`${GATEWAY_URL}/api/scenario/${scenarioId}/geojson`),

  getReport: (scenarioId: string) =>
    fetch(`${GATEWAY_URL}/api/scenario/${scenarioId}/report`),
};
```

### 3.6 행위자 팝업

```tsx
// 행위자 마커 클릭 시 표시되는 팝업
interface ActorPopupData {
  actor: string;
  actor_type: string;
  tension_level: number;
  stance: string;          // supportive | opposing | neutral | cautious_ally
  key_statement: string;
  post_count: number;
  sentiment_avg: number;
}
```

## 4. 마일스톤

- [x] **M1: 시뮬레이션 결과 MapLibre 오버레이** — 완료된 시뮬레이션의 GeoJSON을 MapLibre 레이어로 렌더링. 행위자 Point (circle + label) + 관계 LineString. 행위자 클릭 시 팝업 (입장, 핵심 발언, 긴장 수준). 시뮬레이션 레이어 토글.
  - 검증: 시뮬레이션 완료 → 지도에 행위자 원형 마커 + 관계 라인 표시

- [x] **M2: 시뮬레이션 타임라인 뷰어** — SimulationTimeline 컴포넌트. 라운드별 에이전트 행동 목록 (포스트, 리포스트, 인용). 라운드 슬라이더로 시간 탐색. 에이전트별 필터링.
  - 검증: 라운드 슬라이더 조작 → 해당 라운드의 행동 목록 표시

- [x] **M3: 보고서 뷰어** — ReportViewer 컴포넌트 (마크다운 렌더링). 시나리오 선택 → 보고서 로드. 보고서 없는 시나리오에 대한 빈 상태 처리.
  - 검증: 보고서 마크다운 정상 렌더링

- [x] **M4: E2E 데모** — 남중국해 시나리오 전체 플로우: 시나리오 생성 → 시드 생성 → 시뮬레이션 실행 → 지도 오버레이 + 타임라인 + 보고서. 사용자 개입 없이 자동 진행.
  - 검증: UI에서 시나리오 생성 후 결과까지 전체 플로우 완주

## 5. 성공 기준

- 시뮬레이션 결과가 행위자 마커 + 관계 라인으로 지도에 오버레이된다
- 행위자 클릭 시 입장/긴장수준/핵심발언 팝업이 표시된다
- 타임라인으로 라운드별 에이전트 행동을 탐색할 수 있다
- 예측 보고서를 읽을 수 있다
- 기존 OSINT 레이어와 시뮬레이션 레이어가 동시에 표시된다
- 남중국해 시나리오 E2E 데모가 동작한다

## 6. 위험 및 완화

| 위험 | 완화 |
|------|------|
| MapLibre 성능 (많은 레이어) | 시뮬레이션 레이어는 feature 수가 적음 (국가 수십 개). 성능 문제 없을 것으로 예상 |
| 시뮬레이션 결과가 없는 상태의 UX | 각 컴포넌트에 빈 상태(empty state) 처리. "시뮬레이션을 먼저 실행하세요" 안내 |
| 관계 라인이 너무 많아 시각적으로 복잡 | 강도 임계값 이하 관계 필터링. 관계 레이어 토글 제공 |

## 7. 참고

### 관련 PRD
- **PRD 5 (result-projection)** — GeoJSON 데이터 구조
- **PRD 6a (frontend-foundation)** — 프론트엔드 프로젝트 기반 + MapLibre 지도
- **PRD 6b (scenario-management-ui)** — 시나리오 관리 UI (이 PRD의 선행)

### GeoJSON 구조 (PRD 5에서 정의)
- Point 피처: `feature_type: "actor"` — 행위자 위치 + 속성
- LineString 피처: `feature_type: "relationship"` — 관계 라인 + 속성

## 진행 로그

| 날짜 | 상태 | 내용 |
|------|------|------|
| 2026-03-20 | Draft | PRD 6 분할로 생성 |
