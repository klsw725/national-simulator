# OSINT Simulator V3 - Technical Specification

> Version: 3.0.0
> Date: 2026-03-21
> Status: Complete
> Codename: **Ghostfish v3** — 모듈 통합 + 지능형 파이프라인

---

## 1. Executive Summary

V2에서 구축한 9개 모듈(PostGIS, Action Layer, Entity Resolution, Schema Versioning, Geopolitics Engine, OASIS Platform, Pipeline Checkpoints, Realtime Monitoring, Multi-feed Integration)은 **각각 완전히 동작하지만 서로 연결되지 않았다.**

V3의 핵심 목표: **모듈 간 양방향 데이터 흐름을 구축하여 "OSINT 수집 → 엔티티 해소 → 시드 생성 → 시뮬레이션 → 지정학 분석"의 자동화 파이프라인을 완성한다.**

### V2 → V3 핵심 차이

| V2 | V3 |
|----|-----|
| 모듈이 독립적으로 동작 | 모듈 간 피드백 루프 |
| 시뮬레이션이 블랙박스 | 시뮬레이션 파라미터 완전 제어 |
| 정적 시드 문서 | 웹 검색 + Entity Resolution 기반 시드 |
| 지정학 엔진이 분리 | 지정학 엔진이 시뮬레이션과 양방향 연동 |
| 그래프를 빌드 중에만 볼 수 있음 | 언제든 조회 가능한 그래프 탭 |

---

## 2. V2 아키텍처 갭 분석

### 2.1 현재 데이터 흐름 (V2 — 단방향)

```
ShadowBroker → ObservationCollector → Resolver (dead-end, 결과 미활용)

ShadowBroker → SeedGenerator → SimulationOrchestrator → MiroFish → Results
                                                                      ↓
                                                         GeopoliticsMapper (후처리 레이블링만)

DecisionEngine (독립 실행, 파이프라인과 무관)
```

### 2.2 V3 목표 데이터 흐름 (양방향)

```
ShadowBroker
   ↓
ObservationCollector → observations (PostGIS)
   ↓
Resolver (자동 해소) → resolution_decisions
   ↓                        ↓
   ↓                  resolved entities 컨텍스트
   ↓                        ↓
   ↓  ← ← ← ← ← ← ← ← ← ↓
SeedGenerator + DuckDuckGo 웹 검색
   ↓
SimulationOrchestrator (설정 가능: platform, hours, requirement)
   ↓
MiroFish (agents with tools: search_duckduckgo)
   ↓
Simulation Results
   ↓
GeopoliticsMapper → DecisionEngine (연쇄 이벤트 분석)
   ↓                        ↓
   ↓                  geopolitics_events (DB 저장)
   ↓                        ↓
결과 시각화 + 지정학 보고서
```

### 2.3 발견된 10개 갭

| # | 갭 | 심각도 | V3 PRD |
|---|-----|--------|--------|
| 1 | DecisionEngine이 시뮬레이션 파이프라인과 완전 분리 | Critical | PRD V3-1 |
| 2 | Entity Resolution 결과가 시드 생성에 미활용 | High | PRD V3-2 |
| 3 | observations → 시나리오 생성 연결 없음 | High | PRD V3-2 |
| 4 | SimulationOrchestrator 파라미터 하드코딩 (platform="twitter", simulation_hours=96) | High | PRD V3-3 |
| 5 | GeopoliticsMapper가 후처리 레이블링만 수행 | High | PRD V3-1 |
| 6 | DuckDuckGo 웹 검색 미통합 | High | PRD V3-4 |
| 7 | 그래프 뷰어가 빌드 단계에서만 표시 | Medium | PRD V3-5 |
| 8 | 체크포인트 파이프라인에 지정학 검토 단계 없음 | Medium | PRD V3-1 |
| 9 | simulation_requirement가 전역 상수 (시나리오별 커스터마이징 불가) | Medium | PRD V3-3 |
| 10 | OASIS 통합 테스트 미완 (GeopoliticsPlatform + OasisEnv) | Medium | PRD V3-6 |

---

## 3. V3 PRD 목록

### 실행 순서 및 의존성

```
PRD V3-3 (simulation-params)
  │
  ├──→ PRD V3-2 (intelligent-seed)
  │       │
  │       └──→ PRD V3-1 (geopolitics-integration)
  │               │
  │               └──→ PRD V3-6 (oasis-runtime)
  │
  ├──→ PRD V3-4 (web-search-agents)
  │
  └──→ PRD V3-5 (graph-tab-ui)
```

---

### PRD V3-1: 지정학 엔진 ↔ 시뮬레이션 통합

**문제**: DecisionEngine은 독립 API로만 동작하고, 시뮬레이션 결과를 입력으로 받지 않으며, 시뮬레이션 파이프라인에 영향을 주지 않는다.

**솔루션**:
1. SimulationOrchestrator에서 시뮬레이션 완료 후 DecisionEngine에 결과 주입
2. 시뮬레이션 결과의 에이전트 행동 → GeopoliticsEvent로 변환 → 연쇄 분석
3. 지정학 분석 결과를 geopolitics_events 테이블에 저장
4. 체크포인트 파이프라인에 CP6 (지정학 검토) 추가

**마일스톤**:
- M1: SimulationOrchestrator → DecisionEngine 브릿지 (결과 → 이벤트 변환)
- M2: DecisionEngine 결과 → geopolitics_events DB 저장 + API
- M3: CP6 (지정학 검토) 체크포인트 추가
- M4: 프론트엔드 지정학 분석 뷰 (결과 패널에 통합)

---

### PRD V3-2: 지능형 시드 생성 (ER + Observations 연동)

**문제**: SeedGenerator가 ShadowBroker raw 데이터만 사용하고, Entity Resolution으로 해소된 엔티티 정보와 observations 테이블의 공간 분석 결과를 활용하지 않는다.

**솔루션**:
1. 시드 생성 전에 해당 bbox의 observations 조회 + resolution_decisions 조회
2. 해소된 엔티티의 stix_objects 정보 (타입, 국적, 군사력)를 시드 컨텍스트에 추가
3. PostGIS ST_DWithin 공간 분석으로 엔티티 간 근접 관계 자동 파악
4. 시나리오 ↔ observations 연결 테이블 추가 (감사 트레일)

**마일스톤**:
- M1: SeedGenerator에 Resolver 컨텍스트 주입 (해소된 엔티티 정보)
- M2: PostGIS 공간 분석 → 시드 컨텍스트 (근접 엔티티 관계)
- M3: scenario_observations 연결 테이블 + 감사 트레일
- M4: 프론트엔드 시드 미리보기에 해소된 엔티티 표시

---

### PRD V3-3: 시뮬레이션 파라미터 완전 제어

**문제**: SimulationOrchestrator에서 `platform="twitter"`, `simulation_requirement` (282줄 상수), `seed_filename` 등이 하드코딩되어 시나리오별 커스터마이징이 불가능하다. `total_simulation_hours=96`이 MiroFish에서 설정되어 수천 회 LLM 호출 발생.

**솔루션**:
1. ScenarioConfig에 simulation_params 필드 추가
2. SimulationOrchestrator가 시나리오별 파라미터 사용
3. 프론트엔드 ScenarioForm에서 파라미터 설정 UI
4. MiroFish simulation/start API에 simulation_hours 전달

**파라미터 목록**:

| 파라미터 | 현재 | V3 |
|---------|------|-----|
| platform | `"twitter"` 하드코딩 | 시나리오별 선택 (twitter/reddit) |
| simulation_hours | MiroFish 기본값 96 | 시나리오별 설정 (기본 24) |
| max_rounds | 시나리오에서 전달 | 유지 |
| simulation_requirement | 282줄 전역 상수 | 시나리오별 커스터마이징 |
| entity_resolution_threshold | 0.85 하드코딩 | 환경변수로 조정 |
| geopolitics_enabled | 없음 | 시나리오별 토글 |

**마일스톤**:
- M1: ScenarioConfig 모델 확장 + DB 마이그레이션
- M2: SimulationOrchestrator 파라미터화 (platform, hours, requirement)
- M3: MiroFish Client에 simulation_hours 전달
- M4: 프론트엔드 ScenarioForm 파라미터 UI

---

### PRD V3-4: DuckDuckGo 웹 검색 통합

**문제**: 시뮬레이션 에이전트가 사전 주입된 컨텍스트(시드 문서, 페르소나)에만 의존하고, 실시간 뉴스/정보를 검색할 수 없다.

**솔루션**: 2단계 통합:

1. **시드 보강 (Phase 1)**: 시드 생성 시 DuckDuckGo로 관련 뉴스 검색 → 시드 문서에 "최근 뉴스" 섹션 추가. MiroFish/OASIS 수정 없이 가능.
2. **에이전트 도구 (Phase 2)**: OASIS SocialAgent의 `tools` 파라미터에 `SearchToolkit().search_duckduckgo` 주입. `single_iteration=False` 필수. MiroFish simulation_runner 수정 필요.

**마일스톤**:
- M1: `ddgs` 패키지 의존성 추가 + WebSearchService 생성
- M2: SeedGenerator에 웹 검색 결과 주입 (시드 보강)
- M3: MiroFish simulation_runner에 tools 파라미터 전달 경로 추가
- M4: 프론트엔드에서 웹 검색 활성화 토글 + 검색 키워드 설정

---

### PRD V3-5: 그래프 뷰어 상시 접근

**문제**: GraphViewer가 `simulating:graph_build` 단계에서만 표시되고, 그래프 빌드 완료 후 사라진다.

**솔루션**:
1. SimulationPanel에 "그래프" 탭 추가
2. 시뮬레이션 완료 후에도 `GET /live/graph_data`로 그래프 조회 가능
3. GraphViewer에 노드 클릭 → 엔티티 상세 + 관계 목록 표시

**마일스톤**:
- M1: SimulationPanel에 "그래프" 탭 추가 + GraphViewer 독립 렌더링
- M2: 노드 클릭 인터랙션 (엔티티 상세, 관계 목록, 페르소나 미리보기)
- M3: 그래프 필터링 (엔티티 타입별, 관계 타입별)

---

### PRD V3-6: OASIS 런타임 통합 테스트

**문제**: V2의 GeopoliticsPlatform과 지정학 엔진은 OASIS 런타임 없이 구현됐다. OasisEnv에 GeopoliticsPlatform을 주입하여 실제 시뮬레이션을 실행하는 통합 테스트가 필요하다.

**솔루션**:
1. Docker 환경에 OASIS 패키지 설치
2. GeopoliticsPlatform을 OasisEnv에 주입하는 통합 코드
3. 지정학 액션(DIPLOMATIC_STATEMENT, MILITARY_MOVEMENT 등)이 실제로 실행되는지 검증
4. 기존 Twitter 시뮬레이션과 regression 없는지 확인

**마일스톤**:
- M1: Docker 환경에 OASIS + ddgs 의존성 추가
- M2: GeopoliticsPlatform → OasisEnv 주입 통합 코드
- M3: 지정학 시뮬레이션 E2E 테스트 (3개 국가, 3라운드)
- M4: 기존 Twitter 시뮬레이션 regression 검증

---

## 4. Tech Stack 변경

### 신규 의존성

| 패키지 | 용도 | V3 PRD |
|--------|------|--------|
| `ddgs` | DuckDuckGo 웹 검색 (API 키 불필요) | PRD V3-4 |
| `camel-ai[tools]` | OASIS SearchToolkit 지원 | PRD V3-4, V3-6 |

### 프론트엔드

| 변경 | V3 PRD |
|------|--------|
| SimulationPanel 그래프 탭 | PRD V3-5 |
| ScenarioForm 파라미터 확장 | PRD V3-3 |
| 지정학 분석 뷰 | PRD V3-1 |

---

## 5. 성공 기준

V3 완료의 정의:

- [x] Entity Resolution 결과가 시드 생성에 자동 반영된다
- [x] 시뮬레이션 결과가 지정학 엔진에 자동 주입되어 연쇄 분석이 수행된다
- [x] DuckDuckGo 웹 검색 결과가 시드 문서에 포함된다
- [x] 시뮬레이션 파라미터(platform, hours, requirement)를 시나리오별로 설정할 수 있다
- [x] 그래프 뷰어를 시뮬레이션 완료 후에도 조회할 수 있다
- [x] GeopoliticsPlatform으로 실제 OASIS 시뮬레이션을 실행할 수 있다

---

## 6. 우선순위 및 타임라인

| 주차 | PRD | 핵심 산출물 |
|------|-----|-----------|
| W1 | V3-3 (simulation-params) | 시뮬레이션 파라미터 완전 제어, simulation_hours 설정 |
| W1 | V3-5 (graph-tab-ui) | 그래프 탭 + 노드 인터랙션 |
| W2 | V3-2 (intelligent-seed) | ER → 시드 컨텍스트 주입, PostGIS 공간 분석 |
| W2 | V3-4 M1-M2 (web-search) | DuckDuckGo 시드 보강 |
| W3 | V3-1 (geopolitics-integration) | DecisionEngine ↔ 파이프라인 통합 |
| W4 | V3-4 M3-M4 (web-search agents) | OASIS 에이전트 도구 주입 |
| W4 | V3-6 (oasis-runtime) | GeopoliticsPlatform 통합 테스트 |

---

## 7. Risks & Mitigations

| 리스크 | 심각도 | 완화 |
|--------|--------|------|
| DuckDuckGo 스크래핑 레이트 리밋 | Medium | 검색 결과 캐싱 + 시뮬레이션당 최대 검색 횟수 제한 |
| simulation_hours 축소 시 시뮬레이션 품질 저하 | Medium | 최소 12시간 권장, 품질 메트릭 도입 |
| DecisionEngine + OASIS 동시 실행 시 상태 충돌 | Medium | DecisionEngine은 OASIS 결과를 후처리만 (동시 실행 아님) |
| OASIS 버전 업데이트 시 GeopoliticsPlatform 호환성 | Low | OASIS 버전 고정, 업스트림 모니터링 |

---

## PRD 인덱스

| PRD | 설명 | 상태 |
|-----|------|------|
| [v3-geopolitics-integration.md](prds/v3-geopolitics-integration.md) | 지정학 엔진 ↔ 시뮬레이션 통합 | Complete |
| [v3-graph-tab-ui.md](prds/v3-graph-tab-ui.md) | 그래프 뷰어 상시 접근 | Complete |
| [v3-intelligent-seed.md](prds/v3-intelligent-seed.md) | 지능형 시드 생성 (ER + Observations 연동) | Complete |
| [v3-oasis-runtime.md](prds/v3-oasis-runtime.md) | OASIS 런타임 통합 테스트 | Complete |
| [v3-simulation-params.md](prds/v3-simulation-params.md) | 시뮬레이션 파라미터 완전 제어 | Complete |
| [v3-web-search-agents.md](prds/v3-web-search-agents.md) | DuckDuckGo 웹 검색 통합 | Complete |
