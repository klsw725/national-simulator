# PRD-4: Gateway v2 API 레이어 완성

> Status: Draft
> Priority: Critical (프론트엔드 22개 엔드포인트 중 19개 미동작)
> Dependencies: PRD-0 ~ PRD-3 완료
> Effort: 1일

---

## 1. 배경

PRD-3에서 MiroFish 기반 레거시 라우터 3개(`simulation_run.py`, `simulation_live.py`, `simulation_events.py`)를 삭제했으나, 대체 v2 엔드포인트는 `start_v2`와 `decide_v2` 2개만 구현됨. 프론트엔드 API 클라이언트(`simulationApi.ts`, `liveApi.ts`, `wargameApi.ts`, `whatifApi.ts`)가 호출하는 19개 엔드포인트가 404를 반환하는 상태.

### 삭제된 엔드포인트 → 프론트엔드 영향

| 카테고리 | 삭제된 엔드포인트 | 프론트엔드 호출자 | 심각도 |
|---|---|---|---|
| **상태 조회** | `GET /status` | `simulationApi.getStatus()` | Critical |
| **결과 조회** | `GET /results` | `simulationApi.getResults()` | Critical |
| **보고서 조회** | `GET /report` | `simulationApi.getReport()` | Critical |
| **워게임 재개** | `POST /continue` | `wargameApi.resumeWargame()` | Critical |
| **워게임 상태** | `GET /wargame_status` | `wargameApi.getWargameStatus()` | Critical |
| **체크포인트** | `GET /checkpoint` | `simulationApi.getCheckpoint()` | High |
| **GeoJSON** | `GET /geojson` | `simulationApi.getGeoJSON()` | High |
| **라이브 액션** | `GET /live/actions` | `liveApi.getLiveActions()` | High |
| **라이브 통계** | `GET /live/stats` | `liveApi.getLiveStats()` | Medium |
| **지정학 이벤트** | `GET /geopolitics/events` | GeopoliticsView | Medium |
| **지정학 타임라인** | `GET /geopolitics/timeline` | SimulationTimeline | Medium |
| **What-If CRUD** | `POST/GET /simulation/whatif` | `whatifApi.*` | High |
| **재시도** | `POST /retry` | `simulationApi.retrySimulation()` | Low |

---

## 2. 설계 원칙

1. **데이터 소스 전환**: MiroFish HTTP 호출 → PostgreSQL 직접 쿼리 + LangGraph 체크포인트 조회
2. **API 경로 유지**: 프론트엔드 API 클라이언트 변경을 최소화하기 위해 기존 URL 패턴 유지 (`/api/scenario/{id}/status` 등)
3. **SSE 보완**: 실시간 데이터는 SSE 스트림으로 전달되지만, 초기 로드/폴백용 REST 엔드포인트 필요
4. **pg_notify 명령 전달**: 시뮬레이션 제어(`continue`, `retry`)는 기존 `sim_commands` 채널 활용

---

## 3. 마일스톤

### M1: 시뮬레이션 상태/결과/보고서 조회 (simulation_query.py)

PostgreSQL `simulation_events` + `simulation_results` + `scenarios` 테이블에서 직접 조회.

| 엔드포인트 | 데이터 소스 | 비고 |
|---|---|---|
| `GET /status` | `scenarios.status` + `simulation_events` 최신 | 기존 `scenarios` 테이블 활용 |
| `GET /results` | `simulation_events` WHERE scenario_id 집계 | JSON 집계 |
| `GET /report` | `simulation_events` WHERE type='report_ready' 최신 payload | LLM 보고서 |
| `GET /geojson` | `stix_objects` + `ontology_edge_history` → GeoJSON 변환 | 온톨로지 기반 |

### M2: 워게임 상태 + 재개 + 체크포인트 (wargame_v2.py)

LangGraph `AsyncPostgresSaver`의 체크포인트 테이블에서 현재 상태 조회.

| 엔드포인트 | 구현 방식 |
|---|---|
| `GET /wargame_status` | `checkpoints` 테이블에서 thread_id=scenario_id의 최신 state 조회 |
| `POST /continue` | `pg_notify sim_commands` → `{"type": "resume_simulation"}` |
| `GET /checkpoint` | `checkpoints` 테이블에서 현재 state의 decision_point 추출 |
| `POST /retry` | `pg_notify sim_commands` → `{"type": "start_simulation", "retry": true}` |

### M3: 라이브 데이터 + 지정학 이벤트 (simulation_data.py)

`simulation_events` + `geopolitics_events` + `action_log` 테이블 쿼리.

| 엔드포인트 | 데이터 소스 |
|---|---|
| `GET /live/actions` | `simulation_events` WHERE type='agent_action' |
| `GET /live/stats` | `simulation_events` 집계 (라운드 수, 액션 수, 최대 긴장도) |
| `GET /geopolitics/events` | `geopolitics_events` WHERE scenario_id |
| `GET /geopolitics/timeline` | `simulation_events` round별 그룹핑 |

### M4: What-If 분기 (whatif_v2.py)

LangGraph 체크포인트 포크 기반. 동일 시나리오의 특정 라운드 체크포인트에서 분기하여 다른 결정으로 재실행.

| 엔드포인트 | 구현 방식 |
|---|---|
| `POST /simulation/whatif` | 체크포인트에서 새 thread_id 생성 → state 복사 → user_decision 주입 → `pg_notify start` |
| `GET /simulation/whatif` | `whatif_branches` 테이블 조회 |
| `GET /simulation/whatif/{bid}` | 특정 분기 상태 + 결과 조회 |
| `GET /simulation/whatif/{bid}/compare` | 원본 vs 분기 simulation_events diff |

### M5: 프론트엔드 API 클라이언트 업데이트

기존 API 클라이언트 파일의 URL 경로가 동일하므로 **변경 불필요** — 백엔드가 같은 경로에 새 구현을 제공.

단, `wargameApi.ts`의 `resumeWargame()`이 호출하는 `/continue` 경로와 `simulation_v2.py`의 `decide_v2` 간 역할 중복 정리 필요.

---

## 4. 성공 기준

- [ ] `simulationApi.getStatus()` → 현재 시뮬레이션 상태 정상 반환
- [ ] `simulationApi.getReport()` → LLM 생성 보고서 반환
- [ ] `wargameApi.getWargameStatus()` → 워게임 페이즈/라운드/긴장도/디시전포인트 반환
- [ ] `wargameApi.resumeWargame()` → 결정 후 시뮬레이션 재개
- [ ] `whatifApi.createWhatIfBranch()` → 체크포인트 분기 생성 + 재실행
- [ ] `whatifApi.getWhatIfComparison()` → 원본/분기 결과 비교

---

## 5. 아키텍처 결정

- **새 라우터 4개**: `simulation_query.py`, `wargame_v2.py`, `simulation_data.py`, `whatif_v2.py`
- **DB 직접 쿼리**: MiroFish HTTP 대신 asyncpg로 `simulation_events`, `checkpoints`, `geopolitics_events` 직접 조회
- **LangGraph 체크포인트 테이블**: `langgraph-checkpoint-postgres`가 자동 생성한 `checkpoints` 테이블에서 state JSON 추출
- **기존 URL 유지**: 프론트엔드 API 클라이언트 변경 최소화
