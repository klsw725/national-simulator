# v12 SPEC: 지정학 인텔리전스 플랫폼

> Status: Draft
> Created: 2026-04-03
> Version: v12.0
> Codename: **Palantir** (Gotham/Foundry-class 지정학 시뮬레이션)
> Dependencies: v11-wargame-loop (DecisionEngine, 워게임 UI), v9-interactive-geopolitics (에이전트 상호작용)

---

## 1. Executive Summary

OSINT 데이터와 뉴스를 실시간으로 수집하여 국가 간 관계 그래프를 구축하고, LLM 에이전트 기반 외교 시뮬레이션을 통해 지역 정세를 예측하며, 사용자가 시뮬레이션에 개입하여 다양한 시나리오를 탐색하는 **지정학 인텔리전스 플랫폼**.

Palantir Gotham/AI Foundry가 하는 것:
- 다원 데이터 소스를 통합된 온톨로지로 매핑
- 엔티티 간 관계를 그래프로 연결
- 분석관이 링크 분석, 패턴 탐지, 시뮬레이션을 수행

우리가 만드는 것:
- ShadowBroker OSINT + GDELT 뉴스 → 지정학 온톨로지로 매핑
- 국가/행위자 관계를 DozerDB 지식 그래프로 구축
- LangGraph 에이전트 기반 외교 시뮬레이션 + 사용자 개입

### 핵심 가치 제안

"남중국해에 중국 구축함이 3척 배치되고, 미국이 대만에 무기 수출을 승인한 상황에서 — 향후 72시간 동안 각국은 어떻게 행동하는가? 만약 한국이 중재를 제안하면?"

---

## 2. 문제 정의

### 2.1 현재 아키텍처의 구조적 문제

현재 시스템은 **소셜미디어 시뮬레이션 위에 지정학 분석을 얹은** 구조다. 본질적으로 우선순위가 뒤집혀 있다.

```
현재:  OSINT → 시드 → 소셜미디어 시뮬레이션(OASIS) → 지정학 분석(부수적)
                              ↑ 핵심                    ↑ 파생물

목표:  OSINT → 온톨로지 → 지정학 시뮬레이션(LangGraph) → 예측/보고서
                              ↑ 핵심
```

### 2.2 통신 아키텍처 문제

6개 레이어를 거치는 3중 폴링 체인:

```
Frontend → HTTP poll(2-5s) → Gateway → HTTP poll(Ns) → MiroFish → subprocess+fileIPC → OASIS
```

| 구간 | 방식 | 지연 |
|---|---|---|
| OASIS ↔ MiroFish | subprocess stdin/stdout + 파일 IPC | 가변 (2-30s) |
| MiroFish ↔ Gateway | HTTP 폴링 (poll_until_done) | 매 폴링 간격 |
| Gateway ↔ Frontend | HTTP 폴링 3중 (useSimulation 5s + useLiveSimulation 2-3s + useWargame SSE+5s) | 2-5s |

### 2.3 온톨로지 문제

두 개의 온톨로지가 존재하며, 둘 다 목적에 맞지 않는다:

| 온톨로지 | 위치 | 용도 | 문제 |
|---|---|---|---|
| MiroFish 온톨로지 | `ontology_generator.py` | 소셜미디어 엔티티 (Student, Celebrity, NGO) | 외교 시뮬레이션과 무관 |
| Gateway STIX2 SDO | `custom_sdo.py` | OSINT 엔티티 (Vessel, Aircraft, Satellite) | 시뮬레이션에 연결되지 않음 |

시뮬레이션 입력으로 사용되는 것은 MiroFish 온톨로지인데, 이것은 "누가 트윗할 수 있는가"를 정의한다. 외교 시뮬레이션에 필요한 "어떤 국가가 어떤 자산으로 어떤 행동을 할 수 있는가"와는 관계가 없다.

### 2.4 삭제 대상 컴포넌트 목록

| 컴포넌트 | 파일 | 줄 수 | 삭제 이유 |
|---|---|---|---|
| MiroFishClient | `backend/app/clients/mirofish.py` | 576 | HTTP 클라이언트 → pg_notify로 대체 |
| SimulationOrchestrator | `backend/app/services/simulation_orchestrator.py` | ~1300 | 수동 상태머신 → LangGraph StateGraph로 대체 |
| EventBus | `backend/app/services/event_bus.py` | ~24 | in-memory Queue → PostgreSQL LISTEN으로 대체 |
| simulation_run.py | `backend/app/routers/simulation_run.py` | ~200 | BackgroundTasks 남용 → Simulation Service로 이관 |
| OASIS 프레임워크 전체 | `external/mirofish-backend/` | 전체 서비스 | LangGraph 에이전트로 대체 |
| SimulationRunner | `mirofish:services/simulation_runner.py` | 1300+ | subprocess 관리 → LangGraph in-process |
| SimulationManager | `mirofish:services/simulation_manager.py` | 544 | LangGraph 상태 관리로 대체 |
| simulation_ipc.py | `mirofish:services/simulation_ipc.py` | 385 | 파일 기반 IPC → in-process 호출 |
| ontology_generator.py | `mirofish:services/ontology_generator.py` | 471 | 소셜미디어 온톨로지 → 지정학 온톨로지로 교체 |
| oasis_profile_generator.py | `mirofish:services/oasis_profile_generator.py` | - | 소셜미디어 프로필 → 국가 행위자 프로필로 교체 |
| geopolitics_mapper.py | `backend/app/geopolitics/mapper.py` | - | POST→diplomatic_statement 간접 매핑 불필요 |
| useLiveSimulation 훅 | `frontend/src/hooks/useLiveSimulation.ts` | ~214 | HTTP 폴링 → SSE 단일 채널로 통합 |

### 2.5 유지/재사용 컴포넌트 목록

| 컴포넌트 | 파일 | 재사용 방식 |
|---|---|---|
| DecisionEngine | `backend/app/geopolitics/engine.py` | LangGraph 노드로 래핑. 긴장도/자원 계산 로직 그대로 사용 |
| GeopoliticalActorState | `backend/app/geopolitics/models.py` | 행위자 상태 모델 유지 |
| STIX2 custom SDO | `backend/app/ontology/custom_sdo.py` | 지정학 온톨로지의 기반으로 확장 |
| OntologyVersioning | `backend/app/ontology/versioning.py` | 스키마 버전 관리 그대로 사용 |
| seed_generator | `backend/app/services/seed_generator.py` | 상황 분석 노드에서 재사용 |
| ShadowBroker 클라이언트 | `backend/app/clients/shadowbroker.py` | OSINT 데이터 수집 그대로 사용 |
| 워게임 UI 컴포넌트 (25개+) | `frontend/src/components/wargame/` | 이벤트 타입만 맞추면 대부분 유지 |
| PostgreSQL 스키마 대부분 | `backend/app/database.py` | scenarios, geopolitics_events, decision_points 유지 |
| MapLibre 지도 | `frontend/src/components/map/` | 군사이동, 영향권 시각화에 그대로 사용 |
| useDataPolling 훅 | `frontend/src/hooks/useDataPolling.ts` | OSINT 대시보드용으로 유지 (시뮬레이션과 분리) |
| useWargame 훅 (SSE 부분) | `frontend/src/hooks/useWargame.ts` | SSE 이벤트 타입 변경 후 재사용 |

---

## 3. 목표 아키텍처

### 3.1 서비스 토폴로지

```
┌──────────────────────────────────────────────────────────────────────┐
│  Frontend (Next.js, :8090)                                          │
│  └── SSE 단일 채널 ←─────────────────── Gateway                     │
│  └── HTTP (OSINT 대시보드, 시나리오 CRUD) → Gateway                  │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Gateway Service (FastAPI, :4000)                                    │
│  ├── Frontend API (시나리오 CRUD, 워게임 UI, OSINT 프록시)            │
│  ├── SSE 스트리밍 (PostgreSQL LISTEN → 프론트엔드 SSE 변환)           │
│  ├── 사용자 개입 릴레이 (HTTP → PostgreSQL NOTIFY → Simulation)       │
│  └── 세션/인증 관리                                                   │
│                                                                      │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Simulation Service (FastAPI + LangGraph, :5001)                     │
│  ├── 지정학 온톨로지 관리 (엔티티/관계 유형 정의, 버전 관리)            │
│  ├── 지식 그래프 관리 (DozerDB 연동, 엔티티 추출/연결)                 │
│  ├── OSINT → 엔티티 매핑 (ShadowBroker 데이터 → 온톨로지 노드)        │
│  ├── LangGraph StateGraph (시뮬레이션 엔진 — §5 참조)                 │
│  └── PostgreSQL NOTIFY (이벤트 발행 — §6 참조)                        │
│                                                                      │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Shared Infrastructure                                               │
│  ├── PostgreSQL ── 상태, LangGraph 체크포인트, 시나리오, 이벤트 버스   │
│  ├── DozerDB (Neo4j) ── 지정학 지식 그래프                            │
│  └── ShadowBroker (:8000) ── OSINT 데이터 수집 (변경 없음)            │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### 3.2 설계 원칙

1. **온톨로지 중심** — 모든 데이터는 지정학 온톨로지를 통해 의미적으로 연결된다. 온톨로지 없이 시뮬레이션에 데이터가 들어가지 않는다.
2. **푸시 기반 통신** — 서비스 간 통신은 PostgreSQL NOTIFY로 한다. HTTP 폴링 금지.
3. **관심사 분리** — Gateway는 사용자를 위한 서비스, Simulation Service는 분석을 위한 서비스.
4. **LangGraph 네이티브** — 상태 관리, 체크포인트, 스트리밍을 LangGraph 내장 기능으로 처리한다. 수동 구현 금지.
5. **직접 시뮬레이션** — 지정학 행동을 소셜미디어 메타포로 매핑하지 않는다. 에이전트가 직접 외교/경제/군사 행동을 선택한다.

---

## 4. 지정학 인텔리전스 온톨로지

### 4.1 설계 철학

Palantir Gotham의 Dynamic Ontology와 같은 역할: **다원 데이터 소스를 통합된 의미 체계로 연결하는 스키마 레이어**.

현재 `custom_sdo.py`의 STIX2 객체(XVessel, XAircraft, XGeopoliticalActor 등)를 기반으로 확장한다.

### 4.2 엔티티 유형 (Entity Types)

#### 행위자 (Actors)

| 유형 | STIX2 Type | 설명 | 핵심 속성 | OSINT 소스 |
|---|---|---|---|---|
| `x-nation-state` | CustomObject | 국가 | country_code, military_power, economic_power, ideology, alliance_memberships | GDELT, 뉴스 |
| `x-international-org` | CustomObject | 국제기구 | org_type (military_alliance / economic_bloc / political), member_states | GDELT |
| `x-military-force` | CustomObject | 군사 조직 | force_type (navy/air/army/special), parent_nation, operational_area | SB flights, ships |
| `x-intelligence-agency` | CustomObject | 정보기관 | parent_nation, known_operations | 뉴스 |
| `x-non-state-actor` | CustomObject | 비국가 행위자 | actor_subtype (militant/terrorist/separatist), operating_region | GDELT, LiveUAMap |
| `x-key-leader` | CustomObject | 핵심 의사결정자 | title, parent_org, decision_authority | 뉴스 |

#### 자산 (Assets)

| 유형 | STIX2 Type | 설명 | 핵심 속성 | OSINT 소스 |
|---|---|---|---|---|
| `x-vessel` | CustomObject (기존) | 함정 | mmsi, vessel_type, flag_state, navy, hull_number | SB AIS |
| `x-aircraft` | CustomObject (기존) | 항공자산 | icao24, aircraft_type, military_type, country, is_uav | SB ADS-B |
| `x-satellite` | CustomObject (기존) | 위성 | norad_id, mission_type, orbit_type | SB TLE |
| `x-facility` | CustomObject (기존) | 시설 | facility_type, operator, branch | SB military bases |
| `x-weapon-system` | CustomObject (신규) | 무기체계 | weapon_type, range_km, platform_compatible | 뉴스, 무기거래 데이터 |

#### 이벤트 (Events)

| 유형 | STIX2 Type | 설명 | 핵심 속성 | OSINT 소스 |
|---|---|---|---|---|
| `x-geopolitical-event` | CustomObject (기존 확장) | 지정학 이벤트 | event_type, goldstein_scale, source_url | GDELT |
| `x-military-event` | CustomObject (신규) | 군사 이벤트 | event_subtype (exercise/deployment/movement/incident), participants | SB + GDELT |
| `x-economic-event` | CustomObject (신규) | 경제 이벤트 | event_subtype (sanction/trade_deal/aid/investment), affected_sectors | GDELT, 뉴스 |
| `x-diplomatic-event` | CustomObject (신규) | 외교 이벤트 | event_subtype (summit/statement/treaty/protest), formality_level | GDELT, 뉴스 |

#### 지리 (Geography)

| 유형 | STIX2 Type | 설명 | 핵심 속성 | OSINT 소스 |
|---|---|---|---|---|
| `x-strategic-region` | CustomObject (신규) | 전략적 지역 | region_type (sea/land/air_corridor), disputed_by, strategic_value | SB viewport |
| `x-chokepoint` | CustomObject (신규) | 요충지 | chokepoint_type (strait/canal/pass), transit_volume | SB AIS 밀도 |

### 4.3 관계 유형 (Edge Types)

#### 정치/외교 관계

| 관계 | 방향 | 설명 | 시간 속성 |
|---|---|---|---|
| `ALLIED_WITH` | 양방향 | 동맹 관계 | strength: 0.0-1.0, since, treaty_name |
| `HOSTILE_TO` | 양방향 | 적대 관계 | intensity: 0.0-1.0, since |
| `SANCTIONS_AGAINST` | 단방향 | 제재 관계 | sanction_type, effective_date, sectors |
| `DISPUTED_BY` | N:M | 영유권 분쟁 | claim_basis, dispute_intensity |
| `MEDIATES` | 삼항 | 중재 관계 | mediator → dispute(A, B) |

#### 군사 관계

| 관계 | 방향 | 설명 | 시간 속성 |
|---|---|---|---|
| `DEPLOYED_TO` | 단방향 | 자산 배치 | since, operational_status |
| `COMMANDED_BY` | 단방향 | 지휘 관계 | chain_of_command_level |
| `OPERATES_IN` | 단방향 | 활동 지역 | frequency, purpose |
| `ARMS_SUPPLIED_BY` | 단방향 | 무기 공급 | weapon_types, contract_value |

#### 경제 관계

| 관계 | 방향 | 설명 | 시간 속성 |
|---|---|---|---|
| `TRADE_DEPENDENT_ON` | 단방향 | 무역 의존 | sector, dependency_ratio |
| `ENERGY_SUPPLIED_BY` | 단방향 | 에너지 공급 | energy_type, volume |

#### 인과 관계

| 관계 | 방향 | 설명 |
|---|---|---|
| `CAUSES` | 단방향 | A가 B를 직접 야기 |
| `ENABLES` | 단방향 | A가 B를 가능하게 함 |
| `PREVENTS` | 단방향 | A가 B를 억제/방지 |
| `OBSERVED_AT` | 단방향 | OSINT 관측 연결 (엔티티 → 시간/위치) |

### 4.4 OSINT → 온톨로지 매핑 규칙

ShadowBroker 데이터가 온톨로지 엔티티로 변환되는 규칙:

```python
# ShadowBroker ships → x-vessel → DEPLOYED_TO → x-strategic-region → DISPUTED_BY → x-nation-state
{
    "source": "shadowbroker.ships",
    "entity_type": "x-vessel",
    "field_mapping": {
        "name": "ship.name",
        "mmsi": "ship.mmsi",
        "flag_state": "ship.flag",           # ⚠️ SB는 lng 사용 (AGENTS.md 지뢰)
        "vessel_type": "ship.ship_type",
    },
    "auto_edges": [
        {"type": "DEPLOYED_TO", "target_type": "x-strategic-region", "resolve_by": "coordinates"},
        {"type": "COMMANDED_BY", "target_type": "x-military-force", "resolve_by": "flag_state + navy"},
    ]
}

# ShadowBroker flights → x-aircraft → OPERATES_IN → x-strategic-region
{
    "source": "shadowbroker.military_flights",
    "entity_type": "x-aircraft",
    "field_mapping": {
        "icao24": "flight.icao24",
        "aircraft_type": "flight.aircraft_type",
        "country": "flight.country",
    },
    "auto_edges": [
        {"type": "OPERATES_IN", "target_type": "x-strategic-region", "resolve_by": "coordinates"},
    ]
}

# GDELT events → x-diplomatic-event / x-military-event / x-economic-event
{
    "source": "shadowbroker.gdelt",
    "entity_type": "auto_classify",          # LLM이 event 유형 분류
    "classify_prompt": "GDELT 이벤트를 diplomatic/military/economic 중 분류하고 관련 국가를 추출하라",
    "auto_edges": [
        {"type": "CAUSES or ENABLES or PREVENTS", "resolve_by": "llm_analysis"},
        {"type": "involves", "target_type": "x-nation-state", "resolve_by": "actor_codes"},
    ]
}
```

### 4.5 시간 모델 (Temporal Model)

모든 관계는 시간 속성을 가진다. 고담처럼 관계의 변화를 추적한다:

```sql
-- 관계 이력 테이블
CREATE TABLE ontology_edge_history (
    id UUID PRIMARY KEY,
    edge_type TEXT NOT NULL,            -- 'ALLIED_WITH', 'HOSTILE_TO', ...
    source_entity_id TEXT NOT NULL,
    target_entity_id TEXT NOT NULL,
    properties JSONB NOT NULL,          -- strength, intensity 등
    valid_from TIMESTAMPTZ NOT NULL,
    valid_to TIMESTAMPTZ,               -- NULL = 현재 유효
    observed_source TEXT,               -- 어떤 OSINT 소스에서 관측했는가
    scenario_id UUID REFERENCES scenarios(id),  -- 시뮬레이션 맥락
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_edge_history_temporal ON ontology_edge_history (edge_type, valid_from, valid_to);
```

---

## 5. 시뮬레이션 엔진 (LangGraph)

### 5.1 StateGraph 설계

```
                    ┌──────────────┐
                    │    START     │
                    └──────┬───────┘
                           ▼
                ┌──────────────────┐
                │ analyze_situation │ ◄── OSINT + 뉴스 → 현재 정세 요약
                └────────┬─────────┘
                         ▼
                ┌──────────────────┐
                │ build_relations  │ ◄── 엔티티 추출 → DozerDB 그래프 갱신
                └────────┬─────────┘
                         ▼
                ┌──────────────────┐
                │ create_actors    │ ◄── 국가별 에이전트 프로필 생성
                └────────┬─────────┘
                         ▼
                ┌──────────────────┐
                │ configure_sim    │ ◄── 시뮬레이션 파라미터 설정
                └────────┬─────────┘
                         ▼
               ┌───────────────────┐
          ┌───►│   run_round       │ ◄── 에이전트들이 행동 결정 (LLM 병렬 호출)
          │    └────────┬──────────┘
          │             ▼
          │    ┌───────────────────┐
          │    │ calculate_results │ ◄── DecisionEngine: 긴장도, 자원 계산
          │    └────────┬──────────┘
          │             ▼
          │    ┌───────────────────┐
          │    │ check_intervention│ ◄── 사용자 개입 필요? (should_pause 로직 재사용)
          │    └────────┬──────────┘
          │             │
          │    ┌────────┴────────┐
          │    │                 │
          │  continue      interrupt()  ◄── 워게임: 사용자 결정 대기
          │    │                 │
          │    │           (user_input)
          │    │                 │
          │    ▼                 ▼
          │  ┌───────────────────┐
          │  │ apply_decision    │ ◄── 사용자 결정 반영 (override_next_action 재사용)
          │  └────────┬──────────┘
          │           │
          │  ┌────────┴────────┐
          │  │                 │
          │  next_round     complete
          │  │                 │
          └──┘                 ▼
                    ┌──────────────────┐
                    │ generate_report  │ ◄── 인텔리전스 브리핑 생성
                    └────────┬─────────┘
                             ▼
                    ┌──────────────────┐
                    │      END         │
                    └──────────────────┘
```

### 5.2 State 스키마

```python
from typing import TypedDict, Annotated
from langgraph.graph import add_messages

class SimulationState(TypedDict):
    # 시나리오 정보
    scenario_id: str
    seed_text: str                        # OSINT + 뉴스 기반 시드 문서

    # 온톨로지 & 그래프
    ontology_version: str                  # 사용 중인 온톨로지 버전
    graph_id: str                          # DozerDB 그래프 ID
    situation_summary: str                 # LLM이 생성한 현재 정세 요약

    # 행위자
    actors: dict[str, ActorProfile]        # nation_code → 프로필
    actor_states: dict[str, dict]          # nation_code → GeopoliticalActorState (직렬화)

    # 시뮬레이션 진행
    current_round: int
    max_rounds: int
    round_actions: list[dict]              # 현재 라운드의 행동 목록
    action_history: list[dict]             # 전체 행동 이력

    # 지정학 엔진 상태
    tension_levels: dict[str, float]       # actor_pair → 긴장도
    decision_engine_state: dict            # DecisionEngine.serialize_state()

    # 사용자 개입
    decision_point: dict | None            # 현재 결정 포인트 (있으면 interrupt)
    user_decision: dict | None             # 사용자가 내린 결정

    # 메타
    phase: str                             # analyzing | building | simulating | reporting
    status: str                            # running | paused | completed | failed
    messages: Annotated[list, add_messages] # LangGraph 메시지 누적
```

### 5.3 에이전트 행동 모델

각 국가 행위자는 매 라운드 LLM 호출로 행동을 결정한다. 소셜미디어 행동(post, like, repost)이 아닌 **직접적인 외교/경제/군사 행동**을 선택한다.

#### 행동 유형 (Action Types)

```python
DIPLOMATIC_ACTIONS = [
    "issue_statement",          # 공식 성명 발표
    "propose_negotiation",      # 협상 제안
    "recall_ambassador",        # 대사 소환
    "strengthen_alliance",      # 동맹 강화 선언
    "condemn_action",           # 상대국 행동 비난
    "request_mediation",        # 제3자 중재 요청
    "sign_agreement",           # 협정 체결
]

ECONOMIC_ACTIONS = [
    "impose_sanction",          # 제재 부과
    "lift_sanction",            # 제재 해제
    "restrict_trade",           # 무역 제한
    "offer_aid",                # 원조 제공
    "currency_intervention",    # 통화 개입
]

MILITARY_ACTIONS = [
    "deploy_forces",            # 병력 배치
    "conduct_exercise",         # 군사 훈련 실시
    "mobilize_reserves",        # 예비군 동원
    "withdraw_forces",          # 병력 철수
    "establish_no_fly_zone",    # 비행금지구역 설정
    "naval_patrol",             # 해상 순찰
    "cyber_operation",          # 사이버 작전
]

INTELLIGENCE_ACTIONS = [
    "increase_surveillance",    # 감시 강화
    "share_intelligence",       # 정보 공유 (동맹국)
    "conduct_recon",            # 정찰 활동
    "electronic_warfare",       # 전자전 (GPS 재밍 등)
]

META_ACTIONS = [
    "do_nothing",               # 관망
    "internal_focus",           # 국내 문제 집중
]
```

#### 에이전트 프롬프트 구조

```python
ACTOR_SYSTEM_PROMPT = """
당신은 {country_name}의 국가안보 의사결정자입니다.

## 국가 프로필
- 군사력: {military_power}
- 경제력: {economic_power}
- 이념/체제: {ideology}
- 핵심 동맹: {alliances}
- 핵심 이익: {core_interests}
- 행동 성향: {behavior_tendency}

## 현재 상황
{situation_summary}

## 최근 OSINT 관측
{recent_osint_observations}

## 다른 국가들의 최근 행동
{other_actors_recent_actions}

## 당신의 현재 상태
- 긴장 수준: {tension_levels}
- 가용 자원: {available_resources}
- 국내 여론: {domestic_pressure}

## 지시사항
현재 상황을 분석하고, 이번 라운드에서 취할 행동을 1-3개 선택하십시오.
각 행동에 대해:
1. 행동 유형 (위 목록에서 선택)
2. 대상 (어떤 국가/지역에 대한 행동인지)
3. 강도 (low / medium / high)
4. 근거 (왜 이 행동을 선택했는지)

현실적으로 행동하십시오. 과도한 에스컬레이션은 국내 정치적 비용이 발생합니다.
"""
```

#### 행동 → 결과 계산

에이전트의 행동이 결정되면 **DecisionEngine** (기존 코드 재사용)이 수치적 결과를 계산한다:

```python
async def calculate_results_node(state: SimulationState) -> dict:
    """에이전트 행동 → 수치적 결과 계산. DecisionEngine 재사용."""

    engine = DecisionEngine.from_state(state["decision_engine_state"])

    for action in state["round_actions"]:
        # 행동 유형에 따라 긴장도, 자원, 위협 인식 업데이트
        engine.apply_action(
            actor=action["actor"],
            action_type=action["action_type"],
            target=action["target"],
            intensity=action["intensity"],
        )

    # 라운드 종합 분석
    round_result = engine.run_single_round(state["current_round"])

    return {
        "decision_engine_state": engine.serialize_state(),
        "tension_levels": engine.get_tension_levels(),
        "current_round": state["current_round"] + 1,
        "action_history": state["action_history"] + state["round_actions"],
    }
```

### 5.4 LangGraph 체크포인터

LangGraph의 PostgreSQL 체크포인터를 사용한다. 수동 체크포인트 구현을 삭제한다.

```python
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

checkpointer = AsyncPostgresSaver.from_conn_string(DATABASE_URL)

graph = builder.compile(
    checkpointer=checkpointer,
    interrupt_before=["check_intervention"],  # 워게임 개입 지점
)
```

체크포인트가 자동으로 PostgreSQL에 저장되므로:
- 시뮬레이션 일시정지/재개가 자연스럽다
- 서비스 재시작 후에도 상태가 유지된다
- What-if 분기는 `thread_id`를 복제하여 구현한다

---

## 6. 서비스 간 통신 프로토콜

### 6.1 PostgreSQL NOTIFY/LISTEN

추가 인프라 없이 PostgreSQL만으로 서비스 간 실시간 통신을 구현한다.

#### 채널 정의

| 채널 | 방향 | 용도 |
|---|---|---|
| `sim_events` | Simulation → Gateway | 시뮬레이션 이벤트 (라운드 완료, 페이즈 전환, 에이전트 행동) |
| `sim_commands` | Gateway → Simulation | 사용자 명령 (결정, 시작/중지, 파라미터 변경) |

#### 이벤트 포맷

```json
// sim_events: 라운드 완료
{
    "type": "round_complete",
    "scenario_id": "scn_abc123",
    "round": 5,
    "actions_count": 12,
    "max_tension": 0.78,
    "phase": "simulating",
    "timestamp": "2026-04-03T12:00:00Z"
}

// sim_events: 사용자 개입 필요
{
    "type": "intervention_required",
    "scenario_id": "scn_abc123",
    "decision_point": {
        "id": "dp_xyz789",
        "trigger": "tension_threshold_exceeded",
        "actor": "china",
        "options": [...]
    },
    "timestamp": "2026-04-03T12:05:00Z"
}

// sim_events: 에이전트 행동 (실시간 스트리밍)
{
    "type": "agent_action",
    "scenario_id": "scn_abc123",
    "round": 5,
    "actor": "united_states",
    "action_type": "deploy_forces",
    "target": "south_china_sea",
    "intensity": "medium",
    "reasoning": "중국의 함대 배치에 대한 억지력 강화"
}

// sim_commands: 사용자 결정
{
    "type": "user_decision",
    "scenario_id": "scn_abc123",
    "decision_point_id": "dp_xyz789",
    "chosen_action": {
        "actor": "united_states",
        "action_type": "propose_negotiation",
        "target": "china",
        "intensity": "high"
    }
}
```

#### NOTIFY 페이로드 크기 제한 대응

PostgreSQL NOTIFY 페이로드는 8KB 제한이 있다. 큰 데이터는 DB에 저장하고 ID만 NOTIFY한다:

```python
# Simulation Service 측
async def emit_event(pool, event: dict):
    payload = json.dumps(event, ensure_ascii=False)
    if len(payload.encode()) > 7000:
        # 큰 이벤트는 DB에 저장하고 참조 ID만 전송
        event_id = await store_event_to_db(pool, event)
        payload = json.dumps({"type": "event_ref", "event_id": event_id})
    async with pool.acquire() as conn:
        await conn.execute(f"NOTIFY sim_events, '{payload}'")

# Gateway 측
async def on_notification(conn, pid, channel, payload):
    event = json.loads(payload)
    if event["type"] == "event_ref":
        event = await load_event_from_db(event["event_id"])
    await broadcast_sse(event)
```

### 6.2 Gateway SSE 스트리밍

Gateway는 PostgreSQL LISTEN으로 받은 이벤트를 프론트엔드에 SSE로 중계한다.

```python
# Gateway: PostgreSQL LISTEN → SSE 브릿지
@router.get("/api/scenario/{scenario_id}/events")
async def scenario_event_stream(scenario_id: str):
    async def event_generator():
        conn = await asyncpg.connect(DATABASE_URL)
        await conn.add_listener("sim_events", lambda *args: queue.put_nowait(args))

        while True:
            _, _, _, payload = await queue.get()
            event = json.loads(payload)
            if event.get("scenario_id") == scenario_id:
                yield f"event: {event['type']}\ndata: {payload}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

### 6.3 통신 흐름 전체 시퀀스

```
사용자가 시뮬레이션 시작:
  Frontend → POST /api/scenario/{id}/start → Gateway
  Gateway → INSERT INTO simulation_commands → pg_notify('sim_commands', ...)
  Simulation Service ← LISTEN sim_commands
  Simulation Service → LangGraph graph.ainvoke(...)

매 라운드:
  Simulation Service: LangGraph run_round 노드 실행
    → 에이전트 LLM 호출 (병렬)
    → pg_notify('sim_events', '{"type":"agent_action",...}')  ← 실시간
    → DecisionEngine 계산
    → 체크포인트 저장 (PostgreSQL)
    → pg_notify('sim_events', '{"type":"round_complete",...}')
  Gateway ← LISTEN sim_events → SSE → Frontend (즉시)

워게임 개입:
  Simulation Service: check_intervention → interrupt()
    → pg_notify('sim_events', '{"type":"intervention_required",...}')
  Gateway ← LISTEN → SSE → Frontend: 결정 카드 표시
  Frontend → POST /api/scenario/{id}/decision → Gateway
  Gateway → pg_notify('sim_commands', '{"type":"user_decision",...}')
  Simulation Service ← LISTEN → LangGraph resume(user_input=...)
```

---

## 7. 프론트엔드 통합

### 7.1 통신 채널 단일화

현재 3개의 독립 폴링 루프를 **SSE 단일 채널**로 통합한다.

| 현재 | 제안 |
|---|---|
| `useSimulation` — HTTP 5초 폴링 (상태) | SSE `phase_change`, `status_change` 이벤트 |
| `useLiveSimulation` — HTTP 2-3초 폴링 (라운드 데이터) | SSE `round_complete`, `agent_action` 이벤트 |
| `useWargame` — SSE + HTTP 5초 폴백 | SSE 전용 (폴백 불필요, NOTIFY가 안정적) |

#### 새로운 훅 구조

```typescript
// useSimulationStream.ts — SSE 단일 채널
function useSimulationStream(scenarioId: string) {
    const [state, dispatch] = useReducer(simulationReducer, INITIAL_STATE);

    useEffect(() => {
        const es = new EventSource(`/api/scenario/${scenarioId}/events`);

        es.addEventListener("phase_change", (e) => {
            dispatch({ type: "PHASE_CHANGE", payload: JSON.parse(e.data) });
        });

        es.addEventListener("round_complete", (e) => {
            dispatch({ type: "ROUND_COMPLETE", payload: JSON.parse(e.data) });
        });

        es.addEventListener("agent_action", (e) => {
            dispatch({ type: "AGENT_ACTION", payload: JSON.parse(e.data) });
        });

        es.addEventListener("intervention_required", (e) => {
            dispatch({ type: "INTERVENTION", payload: JSON.parse(e.data) });
        });

        es.addEventListener("report_ready", (e) => {
            dispatch({ type: "REPORT_READY", payload: JSON.parse(e.data) });
        });

        return () => es.close();
    }, [scenarioId]);

    return state;
}
```

### 7.2 UI 컴포넌트 변경

대부분의 워게임 UI 컴포넌트는 **유지**한다. 데이터 바인딩만 변경:

| 컴포넌트 | 변경 사항 |
|---|---|
| `WarRoom.tsx` | useWargame → useSimulationStream으로 교체 |
| `BriefingOverlay.tsx` | 데이터 소스만 변경, UI 유지 |
| `DecisionOverlay.tsx` | 결정 옵션 포맷 변경 (소셜미디어 → 외교 행동) |
| `TensionChart.tsx` | 변경 없음 (tension_levels 데이터 형태 동일) |
| `PhaseTimeline.tsx` | phase 이름 변경 (seed → analyzing 등) |
| `LiveActionFeed.tsx` | 소셜미디어 피드 → 외교 행동 피드로 변경 |
| `MapOverlay` | 군사 배치, 제재 영향권 시각화 추가 |
| `useDataPolling` | 변경 없음 (OSINT 대시보드 독립 유지) |

---

## 8. 마이그레이션 전략

### 8.1 Phase 구성

```
Phase 0 (1주)     Phase 1 (2주)        Phase 2 (3주)          Phase 3 (1주)
━━━━━━━━━━━━     ━━━━━━━━━━━━━━      ━━━━━━━━━━━━━━━━      ━━━━━━━━━━━━━━
인프라 준비        Simulation Service   에이전트 엔진           프론트엔드 통합
                  골격 구축             구현                   + 정리

- pg_notify       - LangGraph          - 국가 에이전트         - SSE 훅 통합
  브릿지 구현        StateGraph 골격      프롬프트 설계         - 폴링 훅 삭제
- 온톨로지         - 파이프라인 노드      - 행동 유형 구현       - 워게임 UI 연결
  스키마 정의        (MiroFish 대신)     - DecisionEngine       - MiroFish 서비스
- DB 마이그레이션  - NOTIFY 발행          연동                    제거
  (edge_history)  - Gateway LISTEN     - 워게임 interrupt     - 통합 테스트
                  - 체크포인터 설정       /resume
```

### 8.2 Phase 0: 인프라 준비 (1주)

병렬 구현 가능. 기존 시스템에 영향 없음.

| 작업 | 설명 | 결과물 |
|---|---|---|
| 온톨로지 스키마 확정 | §4의 엔티티/관계 유형을 코드로 정의 | `custom_sdo.py` 확장 |
| DB 마이그레이션 | `ontology_edge_history` 테이블, LangGraph 체크포인트 테이블 | Alembic 마이그레이션 |
| pg_notify 유틸리티 | emit_event, listen_events 헬퍼 함수 | `backend/app/services/pg_notify.py` |
| Gateway LISTEN 브릿지 | PostgreSQL LISTEN → SSE 변환 라우터 | `backend/app/routers/simulation_stream.py` |

**성공 기준**: Gateway가 pg_notify로 받은 테스트 이벤트를 SSE로 프론트엔드에 전달.

### 8.3 Phase 1: Simulation Service 골격 (2주)

MiroFish를 대체하는 새 서비스. 아직 에이전트는 stub.

| 작업 | 설명 | 결과물 |
|---|---|---|
| 서비스 부트스트랩 | FastAPI + LangGraph 기본 설정 | `simulation-service/` 디렉토리 |
| LangGraph StateGraph | §5.1의 노드 골격 구현 | `simulation-service/app/graph.py` |
| 파이프라인 노드 | analyze_situation, build_relations (seed_generator 재사용) | 노드 구현 |
| NOTIFY 발행 | 각 노드 완료 시 sim_events 발행 | pg_notify 연동 |
| LISTEN 수신 | sim_commands로 시작/중지/결정 수신 | 명령 처리 |
| 체크포인터 | AsyncPostgresSaver 설정 | LangGraph 체크포인트 |
| Gateway 연동 | MiroFishClient 대신 pg_notify로 통신 | Gateway 라우터 수정 |

**성공 기준**: 시나리오 생성 → Simulation Service가 파이프라인 실행 → Gateway가 SSE로 진행 상황 전달 → 프론트엔드에서 확인. (에이전트는 "do_nothing" 반환하는 stub)

### 8.4 Phase 2: 에이전트 엔진 (3주)

핵심: OASIS 대체. LLM 에이전트가 외교 행동을 직접 결정.

| 작업 | 설명 | 결과물 |
|---|---|---|
| 행위자 프로필 생성 | OSINT + 뉴스 → 국가별 프로필 LLM 생성 | create_actors 노드 |
| 에이전트 프롬프트 | §5.3의 프롬프트 템플릿 구현 | 프롬프트 파일 |
| 행동 유형 구현 | 외교/경제/군사/정보 행동의 구조화된 출력 | 행동 스키마 |
| DecisionEngine 연동 | 행동 → 긴장도/자원 계산 (기존 코드 래핑) | calculate_results 노드 |
| 워게임 interrupt | should_pause → LangGraph interrupt | check_intervention 노드 |
| OSINT 실시간 주입 | ShadowBroker 데이터 → 시뮬레이션 컨텍스트 | OSINT 매핑 파이프라인 |
| 보고서 생성 | 인텔리전스 브리핑 스타일 보고서 | generate_report 노드 |

**성공 기준**: 전체 워게임 루프가 동작. 사용자가 시나리오 생성 → 시뮬레이션 실행 → 라운드별 에이전트 행동 확인 → 결정 포인트에서 개입 → 결과 확인.

### 8.5 Phase 3: 통합 및 정리 (1주)

| 작업 | 설명 |
|---|---|
| 프론트엔드 SSE 통합 | useSimulationStream 구현, 기존 폴링 훅 제거 |
| 워게임 UI 연결 | WarRoom → 새 SSE 채널, DecisionOverlay → 외교 행동 |
| MiroFish 서비스 제거 | docker-compose에서 mirofish 서비스 삭제 |
| 레거시 코드 정리 | SimulationOrchestrator, MiroFishClient, EventBus 삭제 |
| 통합 테스트 | 전체 E2E 플로우 검증 |

---

## 9. 리스크 및 대응

| 리스크 | 영향 | 대응 |
|---|---|---|
| **LLM 비용** — 에이전트 10개 × 라운드 72개 = 720+ LLM 호출 | 높음 | 라운드당 활성 에이전트 수 제한 (관련 국가만), 작은 모델 사용 옵션, 캐싱 |
| **LLM 지연** — 에이전트 10개 직렬 호출 시 라운드당 30초+ | 높음 | LangGraph `Send` API로 병렬 호출, 에이전트당 타임아웃 |
| **재현성** — LLM 기반 에이전트는 매번 다른 결과 | 중간 | temperature=0 옵션, 시드 고정, 체크포인트에서 분기하여 비교 |
| **pg_notify 손실** — 리스너가 재연결 중이면 이벤트 유실 가능 | 중간 | 이벤트 시퀀스 번호 + catch-up 쿼리 (edge_history 테이블) |
| **DecisionEngine 호환성** — 기존 엔진이 새 행동 유형을 처리하지 못할 수 있음 | 중간 | Phase 2에서 엔진 확장, 기존 API 유지하면서 새 행동 유형 추가 |
| **마이그레이션 중 dual-run** — Phase 1-2 동안 기존 시스템과 새 시스템 병행 | 낮음 | 새 시나리오만 Simulation Service로 라우팅, 기존 시나리오는 MiroFish로 유지 |

---

## 10. 성공 기준

### 기능 기준

- [ ] OSINT 데이터(ShadowBroker)가 온톨로지를 통해 시뮬레이션 컨텍스트로 자동 변환된다
- [ ] 국가 행위자 에이전트가 외교/경제/군사 행동을 직접 선택한다 (소셜미디어 매핑 없음)
- [ ] 사용자가 시뮬레이션 중 결정 포인트에서 개입하여 시나리오를 분기할 수 있다
- [ ] What-if: 같은 시점에서 다른 선택의 결과를 비교할 수 있다
- [ ] 인텔리전스 스타일 보고서가 자동 생성된다

### 성능 기준

- [ ] 이벤트 전달 지연: < 100ms (현재 2-5초)
- [ ] 라운드 실행 시간: < 30초 (에이전트 병렬 호출)
- [ ] SSE 연결 안정성: 재연결 시 이벤트 유실 없음 (시퀀스 번호 기반 catch-up)
- [ ] 시뮬레이션 일시정지/재개: LangGraph 체크포인트에서 < 2초 내 복원

### 아키텍처 기준

- [ ] MiroFish 서비스 제거 (docker-compose에서 삭제)
- [ ] HTTP 폴링 기반 서비스 간 통신 0건
- [ ] 프론트엔드 시뮬레이션 관련 HTTP 폴링 훅 0건
- [ ] 수동 체크포인트 코드 0줄 (LangGraph 내장 사용)
