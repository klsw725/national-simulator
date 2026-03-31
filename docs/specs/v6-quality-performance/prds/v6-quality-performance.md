# PRD: 품질 강화 + 성능 최적화

> Status: Complete
> Created: 2026-03-22
> Dependencies: 없음 (기존 코드 개선)
> 버전: v6.0

---

## 1. 문제 정의

V1–V5 로드맵이 완료되어 기능은 충분하지만, 코드 감사 결과 세 가지 영역에서 기술 부채가 확인되었다:

- **에러 핸들링**: 7개 CRITICAL 이슈 (빈 except 블록, 사일런트 폴백 응답). API가 에러를 200으로 반환하여 클라이언트가 실패를 감지할 수 없는 케이스 다수.
- **프론트엔드 성능**: `useDataPolling`의 24개 독립 useState가 매 폴링 사이클당 ~18회 불필요한 리렌더를 트리거. MaplibreViewer에 viewport culling/clustering 미적용.
- **백엔드 쿼리**: `simulation_results(scenario_id)`, `seeds(scenario_id)` 등 핵심 테이블에 인덱스 누락 (6개). N+1 INSERT 패턴 (2곳). 38회 json.loads 호출 중복.

## 2. 솔루션 개요

3개 트랙으로 병렬 진행:

**트랙 A: 에러 핸들링 표준화**
**트랙 B: 프론트엔드 성능 최적화**
**트랙 C: 백엔드 쿼리 최적화**

## 3. 트랙 A: 에러 핸들링 표준화

### 3.1 API 에러 응답 표준화

현재 일부 엔드포인트가 에러 시 빈 dict `{}` 또는 폴백 값을 200으로 반환. 클라이언트가 "데이터 없음"과 "서비스 실패"를 구분할 수 없다.

수정 대상 (`backend/app/routers/simulation.py`):
- `get_live_actions` (L979): 에러 시 `{"actions": [], "count": 0}` 반환 → 502 반환
- `get_live_graph_data` (L1006): 에러 시 `{}` 반환 → 502 반환
- `get_live_stats` (L1025): 에러 시 `{"status": "unknown"}` 반환 → 502 반환
- `generate_briefing` (L1474): 에러 시 500 반환되지만 로깅 불충분

### 3.2 프론트엔드 에러 상태 전파

현재 `useSimulation.ts`에서 `.catch(() => {})` (L224)로 에러를 삼킴. 프로덕션에서 에러 가시성 없음.

수정 대상:
- `useSimulation.ts`: `.catch(() => {})` → 에러 상태 설정
- `InteractiveSimulationView.tsx`: 제너릭 에러 메시지 → 상세 에러 표시
- `GeopoliticsView.tsx`: `.catch()` 후 사용자 피드백 없음 → 에러 상태 추가

### 3.3 수정 대상 파일

```
backend/app/routers/simulation.py     # 사일런트 폴백 → 적절한 에러 코드
frontend/src/hooks/useSimulation.ts   # 에러 삼킴 → 에러 상태
frontend/src/components/simulation/InteractiveSimulationView.tsx  # 에러 상세
frontend/src/components/simulation/GeopoliticsView.tsx            # 에러 상태
```

## 4. 트랙 B: 프론트엔드 성능 최적화

### 4.1 폴링 상태 통합 (리렌더 90% 감소)

현재 `useDataPolling.ts`에 24개 독립 `useState`. 매 pollFast 완료 시 ~10회 setState → ~10회 리렌더.

변경: 단일 상태 객체 + useReducer로 배치 업데이트.

```typescript
// Before: 24 individual useState calls
const [ships, setShips] = useState([]);
const [militaryFlights, setMilitaryFlights] = useState([]);
// ... 22 more

// After: single useReducer
const [state, dispatch] = useReducer(pollingReducer, INITIAL_STATE);
// dispatch({ type: 'POLL_FAST', payload: data }) → 1 re-render
```

### 4.2 MaplibreViewer 최적화

| 항목 | 현재 | 목표 |
|------|------|------|
| 팝업 상태 | 13개 독립 useState | 1개 `{ type, data }` 통합 상태 |
| 레이블 minzoom | 없음 (모든 줌에서 렌더) | 라벨 레이어에 minzoom: 6 |
| 클러스터링 | ships만 적용 | flights, satellites, bases 확장 |
| React.memo | 미적용 | MaplibreViewer에 React.memo 래핑 |

### 4.3 코드 스플리팅

현재 SimulationPanel (17개 자식 컴포넌트, 5,569 LOC)이 즉시 로드. OSINTPanel도 마찬가지.

```typescript
// Before
import SimulationPanel from "@/components/simulation/SimulationPanel";
import OSINTPanel from "@/components/osint/OSINTPanel";

// After
const SimulationPanel = dynamic(() => import("@/components/simulation/SimulationPanel"), { ssr: false });
const OSINTPanel = dynamic(() => import("@/components/osint/OSINTPanel"), { ssr: false });
```

### 4.4 폴링 안정성

- 요청 중복 방지: in-flight 요청 있으면 스킵
- 에러 백오프: 연속 실패 시 간격 증가 (15s → 30s → 60s)
- 304 비율 기반 적응: 80% 이상 304 응답 시 간격 자동 증가

### 4.5 수정 대상 파일

```
frontend/src/hooks/useDataPolling.ts              # useReducer 전환, 요청 중복 방지, 백오프
frontend/src/components/map/MaplibreViewer.tsx    # 팝업 통합, minzoom, 클러스터링 확장, memo
frontend/src/app/page.tsx                         # dynamic import 확장
```

## 5. 트랙 C: 백엔드 쿼리 최적화

### 5.1 누락 인덱스 추가

```sql
-- CRITICAL: 매 요청마다 풀 테이블 스캔
CREATE INDEX idx_simulation_results_scenario ON simulation_results(scenario_id);
CREATE INDEX idx_seeds_scenario ON seeds(scenario_id);

-- HIGH: 복합 필터에 인덱스 부재
CREATE INDEX idx_decision_points_scenario_status ON decision_points(scenario_id, status);
CREATE INDEX idx_scenarios_status ON scenarios(status);
CREATE INDEX idx_action_log_scenario_type ON action_log(scenario_id, action_type);
CREATE INDEX idx_injected_events_scenario_status ON injected_events(scenario_id, status);
```

### 5.2 N+1 INSERT 배치화

현재 루프 내 개별 INSERT:
- `simulation.py:108-114`: scenario_observations 루프 INSERT (100+ 회)
- `simulation_orchestrator.py:293-309`: geopolitics_events 이중 루프 INSERT (200+ 회)

변경: `executemany()` 또는 멀티로우 INSERT.

### 5.3 SELECT * 최적화

52개 `SELECT *` 중 대형 컬럼(results, geojson, checkpoint_data — 각 100KB+)을 불필요하게 로드하는 케이스를 필요 컬럼만 지정하도록 변경.

우선 대상:
- `simulation.py:416`: 시나리오 상태 확인에 `SELECT *` → `SELECT id, status`
- `simulation.py:559`: 결과 조회에 `SELECT *` → 필요 컬럼만

### 5.4 무제한 결과 방지

- `simulation.py:1245`: geopolitics timeline 엔드포인트에 LIMIT 없음 → `LIMIT 10000`
- `data_exporter.py:35`: 내보내기에 LIMIT 없음 → 스트리밍 또는 `LIMIT 50000`

### 5.5 수정 대상 파일

```
backend/app/database.py                          # 6개 인덱스 추가
backend/app/routers/simulation.py                # SELECT *, N+1, LIMIT
backend/app/services/simulation_orchestrator.py  # 배치 INSERT
backend/app/services/data_exporter.py            # LIMIT 추가
```

## 6. 마일스톤

- [x] **M1: 인덱스 추가** — database.py에 6개 인덱스 추가. 코드 변경 없이 쿼리 성능 즉시 개선.
  - 검증: EXPLAIN ANALYZE로 인덱스 사용 확인

- [x] **M2: 에러 핸들링 표준화** — simulation.py의 사일런트 폴백 3곳 → 적절한 HTTP 에러 코드. useSimulation.ts의 에러 삼킴 → 에러 상태 전파. 프론트엔드 컴포넌트 에러 상태 추가.
  - 검증: API 에러 시 클라이언트에서 에러 상태 표시

- [x] **M3: 폴링 상태 통합** — useDataPolling.ts의 24개 useState → useReducer 단일 상태. 배치 업데이트로 리렌더 ~90% 감소.
  - 검증: React DevTools Profiler로 pollFast 시 리렌더 1회 확인

- [x] **M4: MaplibreViewer 최적화** — 13개 팝업 상태 통합, 라벨 minzoom:6, 클러스터링 확장 (flights, satellites, bases), React.memo 래핑.
  - 검증: 20개 레이어 활성 시 FPS ≥ 30

- [x] **M5: 코드 스플리팅** — SimulationPanel, OSINTPanel을 dynamic import. 초기 번들에서 ~200-300KB 절감.
  - 검증: 초기 JS 번들 크기 측정 (before/after)

- [x] **M6: N+1 배치화 + SELECT 최적화** — 루프 INSERT → executemany. SELECT * → 필요 컬럼. 무제한 쿼리 → LIMIT.
  - 검증: 100건 이상 geopolitics INSERT 시 쿼리 수 1회로 감소

- [x] **M7: 폴링 안정성** — 요청 중복 방지, 에러 백오프, 적응형 간격.
  - 검증: 네트워크 에러 시 백오프 동작 + 복구 후 정상 간격 복원

## 7. 성공 기준

- API 에러 시 클라이언트가 에러를 감지하고 사용자에게 표시한다 (사일런트 200 없음)
- pollFast 사이클당 page.tsx 리렌더가 1회로 감소한다 (현재 ~10회)
- simulation_results, seeds 테이블 조회에 인덱스 스캔이 사용된다
- 20개 레이어 활성 시 FPS ≥ 30
- 초기 JS 번들 크기가 200KB+ 감소한다

## 8. 위험 및 완화

| 위험 | 완화 |
|------|------|
| useReducer 전환 시 기존 컴포넌트 인터페이스 변경 | PollingResult 인터페이스 유지, 내부만 변경 |
| 에러 응답 변경으로 프론트엔드 호환성 깨짐 | 프론트엔드 에러 핸들링 동시 업데이트 |
| 인덱스 추가로 INSERT 성능 소폭 저하 | 읽기 >> 쓰기 비율이므로 전체적으로 이득 |
| React.memo로 인한 props 비교 오버헤드 | GeoJSON은 이미 useMemo로 참조 안정, 비교 비용 미미 |

## 진행 로그

| 날짜 | 상태 | 내용 |
|------|------|------|
| 2026-03-22 | Draft | 코드베이스 감사 기반 품질+성능 PRD 초안 작성 |
| 2026-03-23 | Complete | M1-M7 전체 구현. 6개 인덱스, useReducer 폴링, 에러 표준화, MaplibreViewer 최적화, 코드 스플리팅, 배치 INSERT, 폴링 안정성 |
