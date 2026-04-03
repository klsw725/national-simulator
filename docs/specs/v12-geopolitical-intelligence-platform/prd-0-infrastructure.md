# PRD-0: 인프라 준비

> Phase: 0 / 4
> 예상 기간: 1주
> 선행 조건: 없음 (기존 시스템에 영향 없이 병렬 작업 가능)
> 참조: v12-spec.md §4 (온톨로지), §6 (통신 프로토콜)

---

## 목표

v12 아키텍처의 기반 인프라를 구축한다. 기존 시스템을 건드리지 않고 병렬로 작업하여, Phase 1이 시작될 때 즉시 사용할 수 있는 상태로 만든다.

**이 Phase가 끝나면**: Gateway가 PostgreSQL NOTIFY로 수신한 테스트 이벤트를 SSE로 프론트엔드에 전달할 수 있다.

---

## M1: 지정학 온톨로지 스키마 확장

### 배경

현재 `backend/app/ontology/custom_sdo.py`에 STIX2 커스텀 객체 6종이 정의되어 있다 (XVessel, XAircraft, XSatellite, XFacility, XGeopoliticalEvent, XGeopoliticalActor). 이를 v12-spec §4.2의 전체 온톨로지로 확장한다.

### 작업

1. `backend/app/ontology/custom_sdo.py` 확장 — 신규 엔티티 유형 추가:
   - 행위자: `XNationState`, `XInternationalOrg`, `XMilitaryForce`, `XIntelligenceAgency`, `XNonStateActor`, `XKeyLeader`
   - 자산: `XWeaponSystem` (신규, 기존 4종은 유지)
   - 이벤트: `XMilitaryEvent`, `XEconomicEvent`, `XDiplomaticEvent` (기존 `XGeopoliticalEvent` 확장)
   - 지리: `XStrategicRegion`, `XChokepoint`

2. `backend/app/ontology/edge_types.py` 신규 생성 — 관계 유형 정의:
   - 정치/외교: `ALLIED_WITH`, `HOSTILE_TO`, `SANCTIONS_AGAINST`, `DISPUTED_BY`, `MEDIATES`
   - 군사: `DEPLOYED_TO`, `COMMANDED_BY`, `OPERATES_IN`, `ARMS_SUPPLIED_BY`
   - 경제: `TRADE_DEPENDENT_ON`, `ENERGY_SUPPLIED_BY`
   - 인과: `CAUSES`, `ENABLES`, `PREVENTS`, `OBSERVED_AT`
   - 각 관계는 시간 속성(valid_from, valid_to)과 강도/세부 속성을 포함

3. `backend/app/ontology/mapping_rules.py` 신규 생성 — OSINT → 온톨로지 매핑 규칙:
   - ShadowBroker ships → `x-vessel` → `DEPLOYED_TO` → `x-strategic-region`
   - ShadowBroker flights → `x-aircraft` → `OPERATES_IN` → `x-strategic-region`
   - GDELT events → `x-diplomatic-event` / `x-military-event` / `x-economic-event`
   - 좌표 필드명 주의: ships/flights/satellites는 `lng`, CCTV/KiwiSDR은 `lon` (AGENTS.md 지뢰)

### 결과물

| 파일 | 상태 |
|---|---|
| `backend/app/ontology/custom_sdo.py` | 수정 (12종 추가) |
| `backend/app/ontology/edge_types.py` | 신규 |
| `backend/app/ontology/mapping_rules.py` | 신규 |

### 성공 기준

- 모든 STIX2 CustomObject가 유효한 STIX2 객체로 생성 가능
- 기존 SDO(XVessel 등)의 하위 호환성 유지
- `OntologyVersioning.register()`로 새 스키마 버전을 등록할 수 있음

---

## M2: DB 마이그레이션

### 작업

1. Alembic 마이그레이션 — `ontology_edge_history` 테이블 생성:

```sql
CREATE TABLE ontology_edge_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    edge_type TEXT NOT NULL,
    source_entity_id TEXT NOT NULL,
    target_entity_id TEXT NOT NULL,
    properties JSONB NOT NULL DEFAULT '{}',
    valid_from TIMESTAMPTZ NOT NULL,
    valid_to TIMESTAMPTZ,
    observed_source TEXT,
    scenario_id UUID REFERENCES scenarios(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_edge_history_temporal
    ON ontology_edge_history (edge_type, valid_from, valid_to);
CREATE INDEX idx_edge_history_source
    ON ontology_edge_history (source_entity_id);
CREATE INDEX idx_edge_history_target
    ON ontology_edge_history (target_entity_id);
CREATE INDEX idx_edge_history_scenario
    ON ontology_edge_history (scenario_id);
```

2. Alembic 마이그레이션 — `simulation_events` 테이블 생성 (pg_notify 대용량 이벤트 저장용):

```sql
CREATE TABLE simulation_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scenario_id UUID NOT NULL REFERENCES scenarios(id),
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    sequence_num BIGSERIAL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_sim_events_scenario_seq
    ON simulation_events (scenario_id, sequence_num);
```

3. LangGraph 체크포인트 테이블은 `AsyncPostgresSaver.setup()`이 자동 생성하므로 별도 마이그레이션 불필요. 단, 데이터베이스 연결 설정은 미리 확인.

### 결과물

| 파일 | 상태 |
|---|---|
| `backend/alembic/versions/xxxx_add_v12_tables.py` | 신규 |

### 성공 기준

- `uv run alembic upgrade head` 성공
- 기존 테이블(scenarios, geopolitics_events 등) 영향 없음
- `ontology_edge_history` CRUD 동작 확인

---

## M3: PostgreSQL NOTIFY 유틸리티

### 배경

서비스 간 통신을 PostgreSQL NOTIFY/LISTEN으로 구현한다. 추가 인프라(Redis 등) 없이 기존 PostgreSQL만 사용.

### 작업

1. `backend/app/services/pg_event_bus.py` 신규 생성:

```python
# 발행 측 (Simulation Service → Gateway)
async def emit_event(pool, channel: str, event: dict) -> None:
    """NOTIFY로 이벤트 발행. 8KB 초과 시 DB에 저장 후 참조 ID 전송."""

# 수신 측 (Gateway ← Simulation Service)
async def listen_events(dsn: str, channel: str, callback) -> None:
    """LISTEN으로 이벤트 수신. 재연결 로직 포함."""

# catch-up 쿼리 (재연결 시 유실 이벤트 복구)
async def catch_up_events(pool, scenario_id: str, after_sequence: int) -> list[dict]:
    """simulation_events 테이블에서 누락된 이벤트 조회."""
```

2. 핵심 구현 사항:
   - NOTIFY 페이로드 8KB 제한 대응: 큰 이벤트는 `simulation_events` 테이블에 저장 후 `event_ref` 전송
   - 재연결 로직: 연결 끊김 시 자동 재연결 + `catch_up_events`로 누락 이벤트 복구
   - 시퀀스 번호: 각 이벤트에 `sequence_num` 부여, 프론트엔드 SSE 재연결 시 `Last-Event-ID` 활용

3. 채널 정의:
   - `sim_events`: Simulation → Gateway (라운드 완료, 에이전트 행동, 개입 요청)
   - `sim_commands`: Gateway → Simulation (시작, 중지, 사용자 결정)

### 결과물

| 파일 | 상태 |
|---|---|
| `backend/app/services/pg_event_bus.py` | 신규 |

### 성공 기준

- 단위 테스트: emit → listen → callback 호출 확인
- 8KB 초과 이벤트가 DB 저장 + 참조 ID로 정상 전달
- 연결 끊김 후 재연결 시 누락 이벤트 catch-up 동작

---

## M4: Gateway LISTEN → SSE 브릿지

### 배경

현재 Gateway의 SSE는 `EventBus` (in-memory asyncio.Queue)를 사용한다. 이를 PostgreSQL LISTEN 기반으로 교체한다. 기존 SSE 라우터(`simulation_events.py`)와 병렬로 새 라우터를 추가하여 점진적 전환.

### 작업

1. `backend/app/routers/simulation_stream.py` 신규 생성:

```python
@router.get("/api/scenario/{scenario_id}/stream")
async def scenario_event_stream(scenario_id: str, request: Request):
    """PostgreSQL LISTEN → SSE 브릿지.
    
    - sim_events 채널 구독
    - scenario_id 필터링
    - Last-Event-ID 헤더로 catch-up 지원
    - 30초 heartbeat
    """
```

2. 핵심 구현 사항:
   - `asyncpg` 연결로 `LISTEN sim_events` 실행
   - 수신된 이벤트 중 해당 `scenario_id`만 필터링하여 SSE 전송
   - `Last-Event-ID` 헤더 처리: 재연결 시 `catch_up_events`로 누락 이벤트 전송
   - 30초 간격 heartbeat (`:keepalive\n\n`)
   - 클라이언트 연결 해제 시 LISTEN 정리

3. `backend/app/main.py`에 라우터 등록 (기존 SSE 라우터와 공존)

### 결과물

| 파일 | 상태 |
|---|---|
| `backend/app/routers/simulation_stream.py` | 신규 |
| `backend/app/main.py` | 수정 (라우터 추가) |

### 성공 기준

- `curl -N http://localhost:4000/api/scenario/test/stream` 으로 SSE 연결 확인
- 별도 터미널에서 `SELECT pg_notify('sim_events', '{"scenario_id":"test","type":"test_event"}')` 실행 시 SSE로 수신
- Last-Event-ID 재연결 시 누락 이벤트 catch-up 동작
- 기존 `/api/scenario/{id}/events` SSE 라우터에 영향 없음

---

## 전체 Phase 0 완료 기준

- [ ] 온톨로지 18종 엔티티 + 15종 관계가 코드로 정의됨
- [ ] DB 마이그레이션 성공 (기존 스키마 영향 없음)
- [ ] pg_notify emit/listen 유틸리티 동작
- [ ] Gateway가 `pg_notify`로 받은 테스트 이벤트를 `/api/scenario/{id}/stream` SSE로 프론트엔드에 전달
- [ ] 기존 시스템 (MiroFish, OASIS, 현재 워게임 루프) 정상 동작 유지
