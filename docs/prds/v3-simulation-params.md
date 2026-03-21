# PRD: 시뮬레이션 파라미터 완전 제어

> Status: Draft
> Created: 2026-03-21
> Dependencies: simulation-orchestration, seed-generation
> 관련 스펙: `specs/V3-SPEC.md` PRD V3-3
> 버전: v3.0

---

## 1. 문제 정의

SimulationOrchestrator에서 핵심 시뮬레이션 파라미터가 하드코딩되어 시나리오별 커스터마이징이 불가능하다.

현재 하드코딩된 값:

| 파라미터 | 위치 | 현재 값 |
|---------|------|--------|
| `platform` | `simulation_orchestrator.py:170` | `"twitter"` 고정 |
| `enable_twitter` | `mirofish.py:100` | `True` 고정 |
| `enable_reddit` | `mirofish.py:101` | `False` 고정 |
| `SIMULATION_REQUIREMENT` | `simulation_orchestrator.py:31-52` | 282줄 전역 상수 |
| `seed_filename` | `simulation_orchestrator.py:80` | `"seed_document.md"` 고정 |
| `use_llm_for_profiles` | `mirofish.py:121` | `True` 고정 |

유일하게 설정 가능한 파라미터는 `max_rounds` (1-30, 기본 10)뿐이다.

추가 문제:
- MiroFish 기본 `total_simulation_hours=96`이 수천 회 LLM 호출을 유발하지만, 이를 제어할 수 없음
- `simulation_requirement` 프롬프트가 모든 시나리오에 동일하게 적용되어, 해역/상황에 맞는 커스터마이징 불가
- Reddit 플랫폼을 선택할 방법이 없음

## 2. 솔루션 개요

- **ScenarioConfig 모델 확장** — `simulation_params` 필드 추가 (platform, simulation_hours, simulation_requirement, geopolitics_enabled)
- **SimulationOrchestrator 파라미터화** — 하드코딩 값을 시나리오별 파라미터로 교체
- **MiroFish Client 확장** — `simulation_hours` 파라미터 전달 경로 추가
- **프론트엔드 ScenarioForm 확장** — 파라미터 설정 UI

## 3. 기술 상세

### 3.1 ScenarioConfig 모델 확장

```python
# backend/app/models/scenario.py

class SimulationParams(BaseModel):
    platform: str = Field(default="twitter", pattern="^(twitter|reddit)$")
    simulation_hours: int = Field(default=24, ge=12, le=96)
    simulation_requirement: str | None = None  # None이면 기본 프롬프트 사용
    geopolitics_enabled: bool = Field(default=False)

class ScenarioCreate(BaseModel):
    name: str
    region: ScenarioRegion
    question: str
    max_rounds: int = Field(default=10, ge=1, le=30)
    data_sources: list[str] = Field(default=["ships", "geopolitics"])
    simulation_params: SimulationParams = Field(default_factory=SimulationParams)
```

### 3.2 DB 마이그레이션

`scenarios` 테이블에 `simulation_params` TEXT 컬럼 추가 (JSON 직렬화).

```sql
ALTER TABLE scenarios ADD COLUMN simulation_params TEXT DEFAULT '{}';
```

### 3.3 SimulationOrchestrator 파라미터화

현재 `_step_ontology()`에서 하드코딩된 `SIMULATION_REQUIREMENT`를 시나리오별 값으로 교체:

```python
# 현재 (하드코딩):
await self.mf.generate_ontology(seed_text, SIMULATION_REQUIREMENT, ...)

# 변경:
requirement = params.simulation_requirement or SIMULATION_REQUIREMENT
await self.mf.generate_ontology(seed_text, requirement, ...)
```

`_step_run_simulation()`에서 platform 하드코딩 제거:

```python
# 현재:
await self.mf.start_simulation(sim_id, platform="twitter", max_rounds=max_rounds)

# 변경:
await self.mf.start_simulation(sim_id, platform=params.platform, max_rounds=max_rounds)
```

### 3.4 MiroFish Client 확장

`start_simulation()` 메서드에 `simulation_hours` 파라미터 추가:

```python
async def start_simulation(
    self, simulation_id: str, platform: str = "twitter",
    max_rounds: int = 10, simulation_hours: int | None = None
) -> dict:
    payload = {"simulation_id": simulation_id, "platform": platform, "max_rounds": max_rounds}
    if simulation_hours is not None:
        payload["total_simulation_hours"] = simulation_hours
    # ...
```

`create_simulation()`에 `enable_reddit` 파라미터 추가:

```python
async def create_simulation(
    self, project_id: str, graph_id: str | None = None,
    enable_twitter: bool = True, enable_reddit: bool = False
) -> dict:
    # ...
```

### 3.5 프론트엔드 ScenarioForm 확장

ScenarioForm에 "고급 설정" 접이식 섹션 추가:

| 필드 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| platform | select | "twitter" | 시뮬레이션 플랫폼 (twitter / reddit) |
| simulation_hours | range slider | 24 | 시뮬레이션 시간 (12-96) |
| simulation_requirement | textarea | (빈값=기본) | 커스텀 시뮬레이션 요구사항 |
| geopolitics_enabled | toggle | false | 지정학 분석 활성화 (V3-1 의존) |

### 3.6 수정 대상 파일

```
backend/app/models/scenario.py       # SimulationParams 모델 추가
backend/app/database.py              # scenarios 테이블 컬럼 추가
backend/app/services/simulation_orchestrator.py  # 파라미터 사용
backend/app/clients/mirofish.py      # simulation_hours, enable_reddit 전달
backend/app/routers/scenario.py      # SimulationParams 저장/조회
backend/app/routers/simulation.py    # SimulationParams → orchestrator 전달
frontend/src/components/simulation/ScenarioForm.tsx  # 파라미터 UI
frontend/src/types/simulation.ts     # SimulationParams 타입
frontend/src/hooks/useSimulation.ts  # 파라미터 전달
frontend/src/lib/gatewayApi.ts       # API 요청에 params 포함
```

## 4. 마일스톤

- [x] **M1: ScenarioConfig 모델 확장 + DB 마이그레이션** — SimulationParams 모델 추가. scenarios 테이블에 simulation_params 컬럼 추가. 시나리오 생성/조회 API에서 params 저장/반환.
  - 검증: POST /api/scenario에 simulation_params 포함 → GET /api/scenario/{id}에서 반환

- [x] **M2: SimulationOrchestrator 파라미터화** — SIMULATION_REQUIREMENT를 시나리오별 값으로 교체. platform 하드코딩 제거. geopolitics_enabled 플래그 전달 (V3-1에서 사용).
  - 검증: platform="reddit"로 시나리오 생성 → MiroFish에 reddit 플랫폼으로 전달

- [x] **M3: MiroFish Client에 simulation_hours 전달** — start_simulation()에 simulation_hours 파라미터 추가. create_simulation()에 enable_twitter/enable_reddit 파라미터 추가.
  - 검증: simulation_hours=24로 설정 → MiroFish에 total_simulation_hours=24 전달

- [x] **M4: 프론트엔드 ScenarioForm 파라미터 UI** — "고급 설정" 접이식 섹션에 platform, simulation_hours, simulation_requirement, geopolitics_enabled 추가.
  - 검증: 프론트엔드에서 파라미터 설정 → 시나리오 생성 시 백엔드에 전달

## 5. 성공 기준

- 시나리오별로 platform (twitter/reddit)을 선택할 수 있다
- simulation_hours를 시나리오별로 설정할 수 있다 (기본 24, 범위 12-96)
- simulation_requirement 프롬프트를 시나리오별로 커스터마이징할 수 있다
- geopolitics_enabled 토글로 지정학 분석 활성화/비활성화 가능 (V3-1 의존)
- 기존 기본값(twitter, 기본 프롬프트)으로 생성한 시나리오가 V2와 동일하게 동작한다

## 6. 위험 및 완화

| 위험 | 완화 |
|------|------|
| simulation_hours 축소 시 시뮬레이션 품질 저하 | 최소 12시간 제한. UI에 권장값(24h) 표시 |
| Reddit 플랫폼의 MiroFish 호환성 미검증 | MiroFish simulation/start API에 platform="reddit" 전달 검증 필요 |
| SIMULATION_REQUIREMENT 커스터마이징이 잘못된 온톨로지 생성 유발 | 빈 값이면 기본 프롬프트 사용. 최소 길이 검증 |
| simulation_params 추가로 기존 시나리오 호환성 깨짐 | DB 마이그레이션에 DEFAULT '{}' 설정. 빈 값이면 기본 동작 |

## 7. 참고

### 관련 PRD
- **simulation-orchestration** — 현재 파이프라인 구조 (6단계)
- **v3-geopolitics-integration (V3-1)** — geopolitics_enabled 파라미터 소비처
- **v3-web-search-agents (V3-4)** — web_search_enabled 파라미터 (향후 추가 가능)

### 실제 MiroFish API 참고
- `POST /api/simulation/start` → `{simulation_id, platform, max_rounds, total_simulation_hours}`
- `POST /api/simulation/create` → `{project_id, enable_twitter, enable_reddit}`
- AGENTS.md: API 경로는 snake_case

## 진행 로그

| 날짜 | 상태 | 내용 |
|------|------|------|
| 2026-03-21 | Draft | V3-3 시뮬레이션 파라미터 완전 제어 PRD 초안 작성 |
| 2026-03-21 | M1-M4 완료 | SimulationParams 모델 + DB 마이그레이션 + Orchestrator 파라미터화 + MiroFish Client 확장 + 프론트엔드 고급 설정 UI. platform/simulation_hours/simulation_requirement/geopolitics_enabled 시나리오별 설정 가능. |
