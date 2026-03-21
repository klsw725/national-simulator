# PRD: 그래프 뷰어 상시 접근

> Status: Draft
> Created: 2026-03-21
> Dependencies: simulation-visualization
> 관련 스펙: `specs/V3-SPEC.md` PRD V3-5
> 버전: v3.0

---

## 1. 문제 정의

GraphViewer가 `simulating:graph_build` 단계에서만 표시되고, 그래프 빌드 완료 후 사라진다.

현재 상태 (`IntermediateResults.tsx`):
- GraphViewer는 `pipelineStatus === "simulating:graph_build"` 일 때만 렌더링
- 그래프 빌드가 완료되면 (prepare → running → report → completed) GraphViewer에 접근 불가
- 시뮬레이션 완료 후 엔티티 관계 그래프를 확인할 방법이 없음
- 노드 클릭 시 엔티티 상세 정보가 표시되지 않음 (현재: 이름과 타입만 표시)

현재 GraphViewer 구현 (`GraphViewer.tsx`):
- D3 force-directed 그래프 (SVG 360x240px)
- 노드: 타입별 색상 (person=cyan, organization=amber, location=purple, event=pink)
- 엣지: 라인 + 레이블
- 데이터: `useLiveSimulation` 훅에서 `getLiveGraphData()` (10초 폴링) + `getLiveGraphTask()` (2초 폴링)

## 2. 솔루션 개요

- **SimulationPanel에 "그래프" 탭 추가** — 시뮬레이션 완료 후에도 그래프 조회 가능
- **노드 클릭 인터랙션** — 엔티티 상세 정보, 관계 목록, 페르소나 미리보기
- **그래프 필터링** — 엔티티 타입별, 관계 타입별 필터

## 3. 기술 상세

### 3.1 SimulationPanel 탭 추가

현재 5개 탭 → 6개로 확장:

| 탭 | 현재 | V3 | 표시 조건 |
|---|---|---|---|
| create | ○ | ○ | 항상 |
| progress | ○ | ○ | 항상 |
| list | ○ | ○ | 항상 |
| **graph** | — | **신규** | **graph_build 이후 (graph_build, prepare, running, report, completed)** |
| timeline | ○ | ○ | completed |
| report | ○ | ○ | completed |

```typescript
// SimulationPanel.tsx 수정
type Tab = "create" | "progress" | "list" | "graph" | "timeline" | "report";

// graph 탭 표시 조건: 그래프 빌드 완료 후부터
const showGraphTab = pipelineStatus && [
  "simulating:prepare", "simulating:running", "simulating:report",
  "checkpoint:profiles", "checkpoint:config",
  "completed"
].includes(pipelineStatus.status);
```

### 3.2 GraphViewer 독립 렌더링

현재 GraphViewer는 `IntermediateResults` 내부에서만 렌더링된다. "graph" 탭에서 독립적으로 렌더링하도록 변경.

```typescript
// graph 탭 콘텐츠
{activeTab === "graph" && (
  <GraphViewer
    graphData={sim.liveData.graphData}
    graphTaskStatus={sim.liveData.graphTaskStatus}
    standalone={true}  // 독립 모드: 더 큰 뷰포트
  />
)}
```

독립 모드에서 변경 사항:
- SVG 뷰포트: 360x240 → 전체 패널 너비 (약 380px) × 가용 높이
- 줌/패닝 지원 (D3 zoom behavior)
- 프로그레스 바 제거 (이미 빌드 완료)

### 3.3 노드 클릭 인터랙션

노드 클릭 시 사이드 패널에 엔티티 상세 표시:

```typescript
interface NodeDetail {
  id: string;
  name: string;
  type: string;        // person, organization, location, event
  properties: Record<string, string>;  // 엔티티 속성
  relationships: {
    target: string;
    type: string;       // 관계 타입
    direction: "outgoing" | "incoming";
  }[];
  persona?: {           // 시뮬레이션 에이전트 페르소나 (있을 때)
    role: string;
    background: string;
  };
}
```

구현:
- 노드 클릭 → `onNodeClick(nodeId)` → 패널 하단에 상세 표시
- 관련 엣지 하이라이트
- 클릭한 노드 크기 확대 + 색상 강조

### 3.4 그래프 필터링

```typescript
interface GraphFilters {
  entityTypes: string[];   // ["person", "organization", "location", "event"]
  relationTypes: string[]; // 동적: 그래프에 존재하는 관계 타입
}
```

필터 UI: 체크박스 그룹으로 구현. 기본값 전체 선택.

### 3.5 API 변경

백엔드 API 변경 없음. 기존 `GET /api/scenario/{id}/live/graph_data` 엔드포인트를 시뮬레이션 완료 후에도 사용 가능하도록 보장.

현재 `useLiveSimulation` 훅은 `simulating:graph_build` 단계에서만 graph_data를 폴링한다. graph 탭에서는 **1회성 fetch**로 변경 (폴링 불필요).

### 3.6 수정 대상 파일

```
frontend/src/components/simulation/SimulationPanel.tsx   # "graph" 탭 추가
frontend/src/components/simulation/GraphViewer.tsx        # standalone 모드, 노드 클릭, 필터링
frontend/src/components/simulation/NodeDetailPanel.tsx    # 신규: 노드 상세 패널
frontend/src/hooks/useLiveSimulation.ts                   # graph_data 1회성 fetch 지원
frontend/src/types/simulation.ts                          # NodeDetail, GraphFilters 타입
```

## 4. 마일스톤

- [x] **M1: SimulationPanel에 "그래프" 탭 추가 + GraphViewer 독립 렌더링** — 6번째 탭 "그래프" 추가 (graph_build 완료 이후 표시). GraphViewer standalone 모드 (전체 패널 크기, 줌/패닝). 완료 상태에서 graph_data 1회성 fetch.
  - 검증: 시뮬레이션 완료 후 "그래프" 탭에서 엔티티 그래프 조회 가능

- [x] **M2: 노드 클릭 인터랙션** — 노드 클릭 → NodeDetailPanel 표시 (이름, 타입, 속성, 관계 목록). 클릭 노드 하이라이트 + 관련 엣지 강조. 페르소나 미리보기 (시뮬레이션 에이전트일 경우).
  - 검증: 노드 클릭 시 상세 정보 + 관계 목록 표시. 관련 엣지 하이라이트.

- [x] **M3: 그래프 필터링** — 엔티티 타입별 필터 (체크박스: person, organization, location, event). 관계 타입별 필터 (그래프 데이터에서 동적 추출). 필터 변경 시 실시간 반영.
  - 검증: 특정 엔티티 타입 필터 해제 시 해당 노드/엣지 숨김

## 5. 성공 기준

- 시뮬레이션 완료 후에도 그래프 뷰어를 "그래프" 탭에서 조회할 수 있다
- 노드 클릭 시 엔티티 상세 정보와 관계 목록이 표시된다
- 엔티티 타입별, 관계 타입별 필터링이 동작한다
- 그래프 빌드 중에도 기존 IntermediateResults의 GraphViewer가 정상 동작한다 (하위 호환)

## 6. 위험 및 완화

| 위험 | 완화 |
|------|------|
| 대규모 그래프 (수백 노드) 시 성능 저하 | D3 force simulation 파라미터 조정. 노드 100개 초과 시 클러스터링 |
| GraphViewer standalone 모드와 기존 모드 충돌 | `standalone` prop으로 모드 분리. 기존 IntermediateResults 코드 미수정 |
| graph_data API가 완료 상태에서 빈 응답 | 백엔드에서 simulation_results에 graph_data 캐싱 검토 |
| 패널 크기 제한 (400px 너비) | 최대한 활용. 노드 상세는 패널 하단 또는 오버레이로 |

## 7. 참고

### 관련 PRD
- **simulation-visualization** — 현재 GraphViewer, SimulationPanel 구현
- **v3-geopolitics-integration (V3-1)** — 지정학 분석 뷰도 탭으로 추가 (병행)

### 현재 GraphViewer 구현
- D3 force simulation: forceLink, forceManyBody, forceCenter, forceCollide
- 노드 색상: person=cyan, organization=amber, location=purple, event=pink
- 데이터 폴링: getLiveGraphTask (2초), getLiveGraphData (10초)
- SVG 크기: 360x240px

### 현재 SimulationPanel 탭 구조
- Tab 타입: "create" | "progress" | "list" | "timeline" | "report"
- 조건부 표시: timeline, report는 completed 상태에서만

## 진행 로그

| 날짜 | 상태 | 내용 |
|------|------|------|
| 2026-03-21 | Draft | V3-5 그래프 뷰어 상시 접근 PRD 초안 작성 |
| 2026-03-21 | M1-M3 완료 | "그래프" 탭 추가 (graph_build 이후 표시). GraphViewer standalone 모드 (줌/패닝, 380x320 뷰포트). 노드 클릭 → NodeDetailPanel (이름/타입/관계목록, 하이라이트). 엔티티·관계 타입별 필터 pill UI. GraphTab 신규 컴포넌트 (1회성 fetch). 기존 IntermediateResults 미수정. |
