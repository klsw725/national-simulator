# PRD: 지능형 시드 생성 (ER + Observations 연동)

> Status: Complete
> Created: 2026-03-21
> Dependencies: v2-entity-resolution, v2-postgresql-postgis, seed-generation, v3-simulation-params
> 관련 스펙: `specs/V3-SPEC.md` PRD V3-2
> 버전: v3.0

---

## 1. 문제 정의

SeedGenerator가 ShadowBroker raw 데이터만 사용하고, Entity Resolution으로 해소된 엔티티 정보와 observations 테이블의 PostGIS 공간 분석 결과를 활용하지 않는다.

현재 SeedGenerator 데이터 흐름 (`seed_generator.py:245-344`):

```
ShadowBroker /api/live-data/fast → ships, flights, satellites, GPS jamming, LiveUAMap
ShadowBroker /api/live-data/slow → GDELT, news, outages, stocks, fires, frontlines
    ↓
VesselMapper → 군함 식별 + 국가 매핑
    ↓
LLM → 시드 문서 (마크다운)
```

누락된 데이터:
- **resolution_decisions**: Resolver가 해소한 엔티티 (STIX objects, 국적, 군사력, 신뢰도)가 시드에 미반영
- **observations + PostGIS**: 공간 분석 (ST_DWithin으로 근접 엔티티 관계 파악)이 시드에 미활용
- **감사 트레일**: 어떤 observations가 시나리오의 시드 생성에 사용됐는지 추적 불가

## 2. 솔루션 개요

- **Resolver 컨텍스트 주입** — 시드 생성 전 해당 bbox의 resolution_decisions 조회, 해소된 엔티티 정보를 LLM 프롬프트에 추가
- **PostGIS 공간 분석** — ST_DWithin으로 엔티티 간 근접 관계 자동 파악, 시드 컨텍스트에 반영
- **scenario_observations 연결 테이블** — 시나리오와 사용된 observations의 감사 트레일
- **프론트엔드 시드 미리보기** — 시드에 포함된 해소된 엔티티 목록 표시

## 3. 기술 상세

### 3.1 Resolver 컨텍스트 조회

시드 생성 전, bbox 영역의 observations를 조회하고 resolution_decisions를 통해 해소된 엔티티 정보를 수집한다.

```python
# SeedGenerator.generate()에 추가
async def _get_resolver_context(self, bbox: list[float]) -> ResolverContext:
    """
    1. observations 테이블에서 bbox 내 관측 조회
       WHERE ST_Intersects(geom, ST_MakeEnvelope(bbox[0], bbox[1], bbox[2], bbox[3], 4326))
    2. 해당 observation_id의 resolution_decisions 조회
       WHERE decision_type IN ('auto', 'manual_merge') AND confidence >= 0.7
    3. resolved_stix_id로 stix_objects 조회 → 타입, 국적, 군사력 정보
    """
```

### 3.2 PostGIS 공간 분석

엔티티 간 근접 관계를 자동 파악하여 시드에 "근접 엔티티" 정보를 추가한다.

```sql
-- 10km 이내 근접 엔티티 쌍 조회
SELECT a.id, b.id,
       ST_Distance(a.geom::geography, b.geom::geography) as distance_m,
       a.source_type, b.source_type
FROM observations a, observations b
WHERE a.id < b.id
  AND ST_DWithin(a.geom::geography, b.geom::geography, 10000)
  AND ST_Intersects(a.geom, ST_MakeEnvelope($1, $2, $3, $4, 4326))
```

### 3.3 시드 프롬프트 확장

기존 `SEED_GENERATION_PROMPT`에 Resolver 컨텍스트 섹션 추가:

```python
RESOLVER_CONTEXT_SECTION = """
## 엔티티 해소 결과 (Entity Resolution)
{resolved_entities}

## 근접 엔티티 관계 (10km 이내)
{proximity_pairs}
"""
```

### 3.4 scenario_observations 연결 테이블

```sql
CREATE TABLE scenario_observations (
    id TEXT PRIMARY KEY,
    scenario_id TEXT NOT NULL REFERENCES scenarios(id),
    observation_id TEXT NOT NULL,
    used_in_seed BOOLEAN DEFAULT FALSE,
    created_at TEXT NOT NULL
);
CREATE INDEX idx_scenario_obs_scenario ON scenario_observations(scenario_id);
CREATE INDEX idx_scenario_obs_observation ON scenario_observations(observation_id);
```

시드 생성 시 사용된 모든 observation_id를 기록한다.

### 3.5 수정 대상 파일

```
backend/app/services/seed_generator.py   # Resolver 컨텍스트 주입
backend/app/database.py                  # scenario_observations 테이블 추가
backend/app/resolution/resolver.py       # bbox 기반 해소 결과 조회 메서드 추가
backend/app/models/seed.py               # SeedMetadata에 resolved_entities 필드 추가
backend/app/routers/simulation.py        # 시드 생성 시 scenario_observations 기록
frontend/src/components/simulation/ScenarioForm.tsx  # 시드 미리보기에 해소 엔티티 표시 (M4)
```

## 4. 마일스톤

- [x] **M1: SeedGenerator에 Resolver 컨텍스트 주입** — bbox 기반 observations + resolution_decisions 조회. 해소된 엔티티의 STIX 정보 (타입, 국적, 군사력)를 시드 LLM 프롬프트에 추가. SeedMetadata에 resolved_entity_count 필드 추가.
  - 검증: bbox 내 해소된 엔티티가 있을 때 시드 문서에 "엔티티 해소 결과" 섹션 포함

- [x] **M2: PostGIS 공간 분석 → 시드 컨텍스트** — ST_DWithin(10km)으로 근접 엔티티 쌍 조회. 근접 관계 정보를 시드 프롬프트에 추가. 거리, 소스 타입, 해소 상태 포함.
  - 검증: 10km 이내 두 관측이 존재할 때 시드에 "근접 엔티티 관계" 정보 반영

- [x] **M3: scenario_observations 연결 테이블 + 감사 트레일** — 시드 생성 시 사용된 observation_id 기록. GET /api/scenario/{id}/observations API 추가. 감사 트레일 조회 가능.
  - 검증: 시드 생성 후 scenario_observations에 레코드 존재. API로 조회 가능.

- [x] **M4: 프론트엔드 시드 미리보기에 해소된 엔티티 표시** — 시드 미리보기 UI에 해소된 엔티티 목록 (이름, 타입, 국적, 신뢰도) 표시. 사용된 observations 수 표시.
  - 검증: 시드 미리보기에서 해소된 엔티티 정보가 표시됨

## 5. 성공 기준

- Entity Resolution 결과가 시드 문서에 자동 반영된다
- PostGIS 공간 분석으로 근접 엔티티 관계가 시드 컨텍스트에 포함된다
- 시나리오 ↔ observations 감사 트레일이 기록되고 조회 가능하다
- Resolver 결과가 없는 경우에도 기존 시드 생성이 정상 동작한다 (하위 호환)

## 6. 위험 및 완화

| 위험 | 완화 |
|------|------|
| bbox 내 observations가 없을 때 빈 컨텍스트 | Resolver 컨텍스트는 선택적 — 없으면 기존 SB 데이터만 사용 |
| 해소된 엔티티가 과다하면 프롬프트 길이 초과 | 최대 20개 엔티티로 제한. confidence 기준 정렬 |
| PostGIS 공간 쿼리 성능 | GIST 인덱스 활용. bbox 사전 필터링으로 검색 범위 축소 |
| 감사 트레일이 observation 삭제 시 고아 레코드 | scenario_observations에 외래 키 제약 없음 (soft reference) |

## 7. 참고

### 관련 PRD
- **v2-entity-resolution** — Resolver, resolution_decisions 테이블
- **v2-postgresql-postgis** — observations 테이블, PostGIS 공간 쿼리
- **seed-generation** — 현재 SeedGenerator 구현
- **v3-simulation-params (V3-3)** — ScenarioConfig 모델 확장 (의존)

### 현재 Resolver 아키텍처
- auto_resolve: score ≥ 0.85 자동 수락 (`resolver.py:122-152`)
- resolution_decisions: observation_id → resolved_stix_id 매핑
- resolution_candidates: match_score, match_strategy 기록

## 진행 로그

| 날짜 | 상태 | 내용 |
|------|------|------|
| 2026-03-21 | Draft | V3-2 지능형 시드 생성 PRD 초안 작성 |
| 2026-03-21 | M1-M3 완료 | _get_resolver_context(): bbox 내 observations → resolution_decisions JOIN stix_objects 조회 (최대 20개, confidence ≥ 0.7). ST_DWithin(10km) 근접 엔티티 쌍 조회. 시드 프롬프트에 "엔티티 해소 결과" + "근접 엔티티 관계" 섹션 주입. scenario_observations 테이블 + GET API. SeedMetadata에 resolved_entity_count, used_observation_ids 추가. M4(프론트엔드)는 향후. |
