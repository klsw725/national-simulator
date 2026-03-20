# PRD: Simulation Orchestration

> Status: Draft
> Created: 2026-03-20
> Dependencies: PRD 1 (gateway-api-foundation), PRD 3 (seed-generation)
> 관련 스펙: `specs/MVP-SPEC.md` Section 3.1.3, 4 Phase 2, 11

---

## 1. 문제 정의

MiroFish는 6단계 비동기 파이프라인(온톨로지 생성 → 그래프 빌드 → 시뮬레이션 생성 → 준비 → 실행 → 보고서)으로 동작한다. OSINT Simulator는 이 전체 파이프라인을 단일 API 호출로 트리거하고, 각 단계의 비동기 완료를 폴링하며, 결과를 수집해야 한다.

핵심 과제:
- MVP-SPEC.md의 MiroFish API 엔드포인트가 실제와 다름 (AGENTS.md 경고)
- 각 단계가 비동기 — task_id 기반 폴링 필요
- 실패 시 재시도/복구 전략 필요
- 시뮬레이션 상태를 실시간으로 추적해야 함

## 2. 솔루션 개요

- **MiroFish HTTP 클라이언트** — 실제 API 엔드포인트에 맞춘 비동기 클라이언트
- **Pipeline Orchestrator** — 6단계를 순차 실행하고 비동기 완료를 폴링
- **상태 추적** — 각 단계 진행률을 Gateway DB에 저장
- **시뮬레이션 API** — 시작/상태/중지/결과 엔드포인트

## 3. 기술 상세

### 3.1 MiroFish 실제 API 엔드포인트 (검증 완료)

> **경고**: MVP-SPEC.md의 엔드포인트와 실제가 다름

| 스펙 (잘못됨) | 실제 엔드포인트 | 메서드 | 용도 |
|---|---|---|---|
| `/api/ontology/generate` | **`/api/graph/ontology/generate`** | POST (multipart) | 온톨로지 생성 |
| — | **`/api/graph/build`** | POST | 그래프 빌드 (비동기) |
| — | **`/api/simulation/create`** | POST | 시뮬레이션 생성 |
| — | **`/api/simulation/prepare`** | POST | 시뮬레이션 환경 준비 (비동기) |
| `/api/simulation/run` | **`/api/simulation/start`** | POST | 시뮬레이션 실행 |
| — | **`/api/simulation/stop`** | POST | 시뮬레이션 중지 |
| `/api/profiles/generate` | **`/api/simulation/generate-profiles`** | POST | 에이전트 프로필 생성 |
| — | **`/api/report/generate`** | POST | 보고서 생성 (비동기) |

### 3.2 파이프라인 실행 순서 (6단계)

```
Step 1: POST /api/graph/ontology/generate
  → project_id (동기)
  입력: files (시드 문서 MD), simulation_requirement
  
Step 2: POST /api/graph/build
  → task_id (비동기, 폴링: GET /api/graph/task/{task_id})
  입력: {project_id}
  
Step 3: POST /api/simulation/create
  → simulation_id (동기)
  입력: {project_id, graph_id, enable_twitter: true, enable_reddit: true}
  
Step 4: POST /api/simulation/prepare
  → task_id (비동기, 폴링: POST /api/simulation/prepare/status)
  입력: {simulation_id, use_llm_for_profiles: true}
  ※ 내부적으로 프로필 생성 포함
  
Step 5: POST /api/simulation/start
  → runner_status (실행 시작)
  입력: {simulation_id, platform: "twitter", max_rounds: N}
  폴링: GET /api/simulation/{id}/run-status
  ※ 완료까지 폴링 (runner_status == "completed")
  
Step 6: POST /api/report/generate
  → report_id, task_id (비동기, 폴링: POST /api/report/generate/status)
  입력: {simulation_id}
```

### 3.3 MiroFish HTTP 클라이언트

```python
# backend/app/clients/mirofish.py
class MiroFishClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = httpx.AsyncClient(base_url=base_url, timeout=60.0)

    # Step 1: 온톨로지 생성 (동기)
    async def generate_ontology(
        self, seed_file: bytes, seed_filename: str,
        simulation_requirement: str, project_name: str | None = None
    ) -> dict:
        """POST /api/graph/ontology/generate (multipart/form-data)
        → {project_id, ontology: {entity_types, edge_types}}"""

    # Step 2: 그래프 빌드 (비동기)
    async def build_graph(self, project_id: str) -> str:
        """POST /api/graph/build → task_id"""

    async def get_task_status(self, task_id: str) -> dict:
        """GET /api/graph/task/{task_id} → {status, progress, message}"""

    # Step 3: 시뮬레이션 생성 (동기)
    async def create_simulation(
        self, project_id: str, graph_id: str | None = None
    ) -> dict:
        """POST /api/simulation/create → {simulation_id, ...}"""

    # Step 4: 시뮬레이션 준비 (비동기)
    async def prepare_simulation(self, simulation_id: str) -> dict:
        """POST /api/simulation/prepare → {task_id, ...}"""

    async def get_prepare_status(self, task_id: str) -> dict:
        """POST /api/simulation/prepare/status → {status, progress}"""

    # Step 5: 시뮬레이션 실행
    async def start_simulation(
        self, simulation_id: str, platform: str = "twitter", max_rounds: int = 10
    ) -> dict:
        """POST /api/simulation/start → {runner_status, ...}"""

    async def get_run_status(self, simulation_id: str) -> dict:
        """GET /api/simulation/{id}/run-status → {runner_status, current_round, progress_percent}"""

    async def stop_simulation(self, simulation_id: str) -> dict:
        """POST /api/simulation/stop"""

    # Step 6: 보고서 생성 (비동기)
    async def generate_report(self, simulation_id: str) -> dict:
        """POST /api/report/generate → {report_id, task_id}"""

    async def get_report_status(self, task_id: str) -> dict:
        """POST /api/report/generate/status → {status, progress}"""

    async def get_report(self, report_id: str) -> dict:
        """GET /api/report/{report_id} → {markdown_content, ...}"""

    # 결과 조회
    async def get_simulation_actions(self, simulation_id: str) -> dict:
        """GET /api/simulation/{id}/actions"""

    async def get_simulation_posts(self, simulation_id: str) -> dict:
        """GET /api/simulation/{id}/posts"""

    async def get_simulation(self, simulation_id: str) -> dict:
        """GET /api/simulation/{id}"""
```

### 3.4 Pipeline Orchestrator

```python
# backend/app/services/simulation_orchestrator.py
class SimulationOrchestrator:
    def __init__(self, mf_client: MiroFishClient, db):
        self.mf = mf_client
        self.db = db

    async def run_pipeline(self, scenario_id: str, seed_document: SeedDocument) -> str:
        """
        전체 파이프라인 실행 (비동기 백그라운드 태스크).
        각 단계 완료를 폴링하며, 상태를 DB에 업데이트.
        
        반환: simulation_result_id
        """

    async def _poll_until_done(
        self, poll_fn, interval: float = 5.0, timeout: float = 600.0
    ) -> dict:
        """비동기 태스크 완료까지 폴링. 타임아웃 시 예외."""

    async def get_pipeline_status(self, scenario_id: str) -> dict:
        """현재 파이프라인 진행 상태 조회"""
```

### 3.5 simulation_requirement 프롬프트

MiroFish에 전달하는 시뮬레이션 요구사항 (MVP-SPEC.md Section 11 참조):

```python
SIMULATION_REQUIREMENT = """
해상 안보 시나리오의 지정학적 시뮬레이션입니다.

이 시뮬레이션에서:
- 각 엔티티는 '국가 행위자' 또는 '국제 기구'입니다.
- 엔티티 간에는 동맹 지지, 비난 성명, 중립 선언 등의 상호작용을 합니다.
- 해상 긴장 상황에서 각 행위자의 반응과 여론 전파 경로를 시뮬레이션합니다.

가능한 엔티티 유형:
- Superpower, RegionalPower, SmallState
- MilitaryAlliance, InternationalOrganization
- MediaOutlet, MilitaryCommander, Diplomat
- Person, Organization
"""

ACTION_MAPPING_PROMPT = """
당신은 소셜미디어 플랫폼에서 국가/기관의 공식 계정을 운영합니다.
- 포스트 작성 (CREATE_POST): 공식 성명 또는 입장 발표
- 인용 포스트 (QUOTE_POST): 타국 성명에 대한 공식 반응/논평
- 리포스트 (REPOST): 동맹국 성명 지지/전파
- 좋아요 (LIKE_POST): 타국 성명에 대한 암묵적 동의
- 팔로우 (FOLLOW): 외교적 관계 형성 의사 표시
- 아무것도 안 함 (DO_NOTHING): 전략적 관망/무반응
"""
```

### 3.6 상태 머신

```
시나리오 상태 흐름:
created → seeding → seed_completed → simulating → completed | failed

시뮬레이션 파이프라인 상세 상태:
simulating:ontology → simulating:graph_build → simulating:create
→ simulating:prepare → simulating:running → simulating:report → completed
```

## 4. 마일스톤

- [ ] **M1: MiroFish HTTP 클라이언트 구현** — 위 6단계의 모든 API 호출 메서드 구현. multipart/form-data 온톨로지 요청 포함. 에러 핸들링 + 타임아웃.
  - 검증: MF 실행 상태에서 각 메서드 개별 호출 성공

- [ ] **M2: 비동기 폴링 로직 구현** — `_poll_until_done()` 유틸리티. graph/build, simulation/prepare, report/generate 3개 비동기 단계 폴링. 타임아웃 (기본 10분) + 진행률 로깅.
  - 검증: 비동기 태스크 시작 → 완료까지 폴링 → 결과 반환

- [ ] **M3: Pipeline Orchestrator 구현** — 6단계 순차 실행 로직. 각 단계 완료 후 다음 단계 시작. DB에 상태 업데이트. FastAPI BackgroundTasks로 비동기 실행.
  - 검증: 시드 문서 입력 → 전체 파이프라인 실행 → 시뮬레이션 완료

- [ ] **M4: 시뮬레이션 API 통합** — POST `/api/scenario/{id}/simulate` → 파이프라인 트리거. GET `/api/scenario/{id}/status` → 현재 단계/진행률. GET `/api/scenario/{id}/results` → 시뮬레이션 결과.
  - 검증: API 호출로 파이프라인 시작/상태 조회/결과 조회 동작

- [ ] **M5: 에러 복구 + 재시도** — 각 단계 실패 시 적절한 에러 메시지. 타임아웃 시 시뮬레이션 상태를 "failed"로 업데이트. MiroFish 미기동 시 503 응답.
  - 검증: MF 미기동 시 명확한 에러 응답. 타임아웃 시 상태 정상 전이

- [ ] **M6: E2E 검증** — 시드 문서 → MiroFish 온톨로지 → 그래프 → 시뮬레이션 → 보고서 전체 파이프라인 성공. 결과가 DB에 저장.
  - 검증: `POST /api/scenario/{id}/simulate` → 상태 폴링 → `GET /results` → 시뮬레이션 데이터 반환

## 5. 성공 기준

- 단일 API 호출로 MiroFish 6단계 파이프라인이 자동 실행된다
- 각 단계의 진행 상태를 실시간으로 조회할 수 있다
- 파이프라인 완료 후 시뮬레이션 결과(포스트, 액션, 보고서)를 조회할 수 있다
- 실패/타임아웃 시 적절한 상태 전이와 에러 메시지가 제공된다
- MiroFish 미기동 시 명확한 에러 응답을 반환한다

## 6. 위험 및 완화

| 위험 | 완화 |
|------|------|
| MiroFish 파이프라인 실행 시간이 길다 (수십 분) | 각 단계별 타임아웃 설정. 폴링 간격 조절. 프론트엔드에 진행률 표시 (PRD 6) |
| 온톨로지가 지정학 도메인에 부적합 | simulation_requirement 프롬프트 정교화. 온톨로지 수동 보정 옵션은 v2에서 추가 |
| OASIS 시뮬레이션이 비현실적 결과 생성 | 에이전트 persona에 행동 가이드 포함 (action_mapping_prompt). max_rounds 제한 |
| MiroFish API 응답 구조 변경 | 클라이언트 어댑터 패턴으로 격리. 응답 파싱을 클라이언트 내부에 캡슐화 |
| LLM API 비용 (시뮬레이션 라운드당 LLM 호출) | max_rounds 기본값 10. 비용 추적 로깅 |

## 7. 참고

### 관련 PRD
- **PRD 3 (seed-generation)** — 시드 문서 제공
- **PRD 5 (result-projection)** — 시뮬레이션 결과를 GeoJSON으로 변환

### MiroFish 파이프라인 주의사항
- `LLM_BOOST_API_KEY` 환경변수가 `.env`에 존재하면 안 됨 (AGENTS.md 경고)
- 온톨로지 생성은 `multipart/form-data`로 파일 업로드 필요
- `simulation/prepare`는 내부적으로 프로필 생성을 포함 (별도 generate-profiles 호출 불필요)
- `simulation/start`의 platform은 "twitter", "reddit", "parallel" 중 선택

### 소스 프로젝트 참조
- MiroFish API: `/home/swlee/mirofish-ko/backend/app/api/` (graph.py, simulation.py, report.py)
- Flask 앱: `/home/swlee/mirofish-ko/backend/app/__init__.py`

## 진행 로그

| 날짜 | 상태 | 내용 |
|------|------|------|
| 2026-03-20 | Draft | PRD 초안 작성 |
