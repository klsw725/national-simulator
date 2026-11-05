# OSINT Simulator (Ghostfish)

실시간 OSINT와 뉴스를 바탕으로 국가 간 관계 그래프를 만들고, LLM 국가 에이전트가 라운드마다 외교·경제·군사·정보 행동을 고르는 지정학 시뮬레이션 플랫폼입니다. 분석관은 파이프라인 단계와 라운드 중간에 개입해 결정을 내리고, What-If 분기로 다른 전개를 비교할 수 있습니다.

> v11까지는 MiroFish(OASIS 기반 멀티 에이전트 엔진)를 확장해 썼습니다. MiroFish 온톨로지는 "누가 SNS에서 발언하는가"를 기준으로 만들어져 국가 간 시뮬레이션과 맞지 않았고, v12에서 MiroFish와 OASIS를 걷어내고 자체 지정학 온톨로지와 LangGraph 기반 시뮬레이션 서비스로 교체했습니다. 코드명 Ghostfish는 초기에 쓰던 두 외부 서비스 MiroFish와 ShadowBroker에서 따왔습니다.

---

## 아키텍처

```mermaid
flowchart TB
    FE["Frontend<br/>Next.js 16 · :8090"]
    GW["Gateway API<br/>FastAPI · :4000"]
    SIM["Simulation Service<br/>FastAPI + LangGraph · :5001"]
    PG[("PostgreSQL 16 + PostGIS<br/>:5432")]
    DZ[("DozerDB<br/>Neo4j 호환 · :7687")]
    SB["ShadowBroker<br/>OSINT 수집 · :8000"]

    FE -- "HTTP / SSE" --> GW
    GW -- "HTTP" --> SB
    GW -- "NOTIFY sim_commands<br/>LISTEN sim_events" --> PG
    SIM -- "LISTEN sim_commands<br/>NOTIFY sim_events<br/>체크포인트" --> PG
    SIM -- "Bolt" --> DZ
    SIM -- "HTTP" --> SB
```

- Gateway는 사용자 요청을, Simulation Service는 시뮬레이션을 맡습니다. 두 서비스는 HTTP로 직접 통신하지 않고 PostgreSQL `LISTEN/NOTIFY`로 주고받습니다.
  - 명령(`sim_commands`): `start_simulation`, `stop_simulation`, `user_decision`, `resume_simulation`, `start_whatif`
  - 이벤트(`sim_events`): Simulation Service → Gateway → SSE → Frontend
- 이벤트는 `simulation_events` 테이블에 순번과 함께 저장한 뒤 알립니다. 7KB를 넘는 이벤트는 참조만 보내고, 연결이 끊긴 클라이언트는 `Last-Event-ID`로 놓친 이벤트를 다시 받습니다.

---

## 시뮬레이션 파이프라인

LangGraph `StateGraph`로 구성했습니다. 상태는 PostgreSQL 체크포인트에 저장되어 중단 후 재개할 수 있습니다.

| 순서 | 노드 | 하는 일 |
|---|---|---|
| 1 | `analyze_situation` | 시드 문서와 최신 OSINT로 정세 요약 생성 |
| 2 | `build_relations` | 정세 요약에서 엔티티·관계를 LLM으로 추출해 DozerDB에 저장 |
| 3 | `create_actors` | 국가 행위자 프로필 생성, 그래프의 관계 타입·강도로 동맹·적대 초기화 |
| 4 | `configure_sim` | 라운드·긴장도 상태 초기화 |
| 5 | `simulation_loop` (서브그래프) | `run_round` → `calculate_results` → `evaluate_events` 반복, 분석관 결정이 있으면 `apply_decision` |
| 6 | `generate_report` | 인텔리전스 브리핑 생성 |

- `run_round`: 국가 에이전트마다 LLM을 병렬로 호출해 행동 25종(외교 7, 경제 5, 군사 7, 정보 4, 기타 2) 중에서 고릅니다. 라운드마다 최신 OSINT 요약을 함께 넣습니다.
- `calculate_results`: 결정 엔진이 행동을 적용해 긴장도와 자원을 갱신하고, 동맹·적대 관계를 따라 연쇄 반응을 계산합니다.

### 분석관 개입

- **단계별 검토 모드**: 시드, 그래프, 프로필, 설정 4개 지점에서 멈추고 검토 후 진행합니다.
- **라운드 중 결정(HIT)**: 다음 조건에서 시뮬레이션을 멈추고 분석관의 결정을 받습니다.
  - 연쇄 반응 발생
  - 고강도 군사 행동(병력 배치·군사 이동·사이버 작전, 강도 0.7 이상)
  - 최대 긴장도 0.6 이상
  - 전략 방향 결정(2라운드, 이후 3라운드마다)
  - 앞의 두 조건은 직전 개입 후 2라운드 동안 다시 묻지 않습니다.
- **What-If 분기**: 특정 라운드에서 다른 결정을 넣어 분기를 만들고 원래 결과와 비교합니다.

---

## 지정학 온톨로지

`stix2` 라이브러리로 STIX 2.1 커스텀 객체를 정의합니다. OpenCTI 전체를 도입하는 대신 라이브러리만 썼습니다.

**엔티티 17종** (`backend/app/ontology/custom_sdo.py`)

| 범주 | 타입 |
|---|---|
| 행위자 (6) | `x-nation-state`, `x-international-org`, `x-military-force`, `x-intelligence-agency`, `x-non-state-actor`, `x-key-leader` |
| 자산 (5) | `x-vessel`, `x-aircraft`, `x-satellite`, `x-facility`, `x-weapon-system` |
| 이벤트 (4) | `x-geopolitical-event`, `x-military-event`, `x-economic-event`, `x-diplomatic-event` |
| 지리 (2) | `x-strategic-region`, `x-chokepoint` |

**관계 15종** (`backend/app/ontology/edge_types.py`): 관계마다 방향(단방향, 양방향, N:M, 삼항)과 강도·시간 속성을 정의합니다.

| 범주 | 관계 |
|---|---|
| 정치·외교 (5) | `ALLIED_WITH`, `HOSTILE_TO`, `SANCTIONS_AGAINST`, `DISPUTED_BY`, `MEDIATES` |
| 군사 (4) | `DEPLOYED_TO`, `COMMANDED_BY`, `OPERATES_IN`, `ARMS_SUPPLIED_BY` |
| 경제 (2) | `TRADE_DEPENDENT_ON`, `ENERGY_SUPPLIED_BY` |
| 인과 (4) | `CAUSES`, `ENABLES`, `PREVENTS`, `OBSERVED_AT` |

- 시뮬레이션 그래프 추출에는 현재 이 중 엔티티 4종(`NationState`, `MilitaryForce`, `StrategicRegion`, `InternationalOrg`)과 관계 6종(`ALLIED_WITH`, `HOSTILE_TO`, `DEPLOYED_TO`, `SANCTIONS_AGAINST`, `OPERATES_IN`, `TRADE_DEPENDENT_ON`)을 씁니다.
- 스키마 버전은 해시와 함께 `ontology_versions` 테이블에 기록하고, 버전 간 차이는 `/api/ontology/versions/diff`로 조회합니다.

---

## OSINT 데이터 흐름

- **수집**: 외부 프로젝트 ShadowBroker가 선박(AIS), 항공기(ADS-B), 위성, GDELT, CCTV, SDR 등을 수집합니다.
- **2계층 저장**: 원시 관측(Tier 1)은 수정하지 않고 좌표(Point, EPSG:4326)와 함께 `observations`에 저장합니다. 해소된 엔티티(Tier 2)는 STIX JSON으로 `stix_objects`에 둡니다.
- **엔티티 해소**: MMSI·IMO·ICAO24·NORAD 식별자가 같으면 1.0, 이름 유사도 0.6 이상이면 후보로 올리고, 0.85 이상은 자동 병합합니다. 나머지는 분석관이 검토 대기열에서 수락·거부·병합하며, 모든 결정은 이력으로 남습니다.
- **GDELT**: 5분마다 수집해 CAMEO 루트 코드로 외교·경제·군사 이벤트를 나누고, Goldstein 척도를 강도로 씁니다.
- **시드 생성**: 시나리오 지역의 OSINT, GDELT, 웹 검색 결과로 시나리오 문서를 만듭니다. 해소된 엔티티가 있으면 그 목록과 10 km 이내 근접 관측 쌍을 근거로 덧붙입니다.

---

## 저장소 역할

| 저장소 | 담당 |
|---|---|
| PostgreSQL 16 + PostGIS | 시나리오·시드·결과, 원시 관측(GIST 공간 인덱스), 해소 엔티티와 해소 이력, 온톨로지 버전, 관계 이력(유효 기간), 시뮬레이션 이벤트, LangGraph 체크포인트, 서비스 간 메시지 |
| DozerDB (Neo4j 호환) | 시나리오별 행위자 관계 그래프. `graph_id`로 시나리오를 나누고 `(:Entity)-[:RELATES_TO]->(:Entity)`로 저장 |

좌표·시간이 있는 대량 관측과 영역·반경 질의는 PostGIS가, 행위자 사이의 관계는 그래프 DB가 맡습니다. 상태 저장과 서비스 간 메시지는 별도 브로커 없이 PostgreSQL 하나로 처리합니다.

---

## 주요 기능

- **시나리오**: 생성, 목록, 비교, OSINT 기반 시드 생성
- **시뮬레이션**: 실시간 진행 스트리밍, 워룸 화면, 라운드 타임라인, 분석관 결정, What-If 분기
- **분석**: 관계 그래프, 지정학 타임라인, 인텔리전스 리포트와 내보내기, AI 코파일럿 대화
- **인과 분석**: 시뮬레이션 기록으로 인과 구조 학습(pgmpy), 개입·반사실·기여도 분석(DoWhy), LLM 인과 서술
- **OSINT 패널**: 지도(MapLibre GL), 피드, 시계열 추세, 이상 탐지, 데이터 최신성
- **운영**: 서비스 헬스 대시보드, 서킷 브레이커, 작업 감사 로그

---

## 기술 스택

| 영역 | 기술 |
|---|---|
| Gateway | Python 3.12, FastAPI, asyncpg, httpx, stix2, OpenAI SDK, DuckDuckGo Search, networkx, pgmpy, DoWhy, scikit-learn, Alembic |
| Simulation Service | Python 3.12, FastAPI, LangGraph(PostgreSQL 체크포인트), OpenAI SDK, neo4j 드라이버, asyncpg |
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS 4, MapLibre GL, D3.js, Recharts, lightweight-charts |
| Database | PostgreSQL 16 + PostGIS 3.4, DozerDB 5.26 (Neo4j 호환) |
| LLM | OpenAI 호환 API (기본값: Qwen `qwen-plus`) |
| Infra | Docker Compose, uv, npm |

---

## 빠른 시작

### 사전 요구사항

- Docker, Docker Compose
- 로컬 개발 시: uv, Node.js 20+

### 1. 환경 설정

```bash
cp .env.example .env
# .env에 LLM_API_KEY 설정

cp external/Shadowbroker-backend/.env.example external/Shadowbroker-backend/.env
# OPENSKY_CLIENT_ID, OPENSKY_CLIENT_SECRET, AIS_API_KEY 설정
```

### 2. 전체 실행

```bash
docker compose up -d
```

| 서비스 | 주소 |
|---|---|
| frontend | http://localhost:8090 |
| gateway | http://localhost:4000 (Swagger: `/docs`) |
| simulation-service | http://localhost:5001/health |
| shadowbroker | http://localhost:8000 |
| postgres | localhost:5432 |
| dozerdb | http://localhost:7474 (Browser), bolt://localhost:7687 |

DB 스키마는 Alembic으로 적용합니다(`cd backend && uv run alembic upgrade head`). Gateway도 시작할 때 기본 스키마를 만들어 둡니다.

### 3. 로컬 개발

인프라만 컨테이너로 띄웁니다.

```bash
docker compose up -d postgres dozerdb shadowbroker
```

Gateway:

```bash
cd backend
uv sync
uv run uvicorn app.main:app --host 0.0.0.0 --port 4000 --reload
```

Simulation Service(로컬에서 실행할 때는 DozerDB 주소를 바꿉니다):

```bash
cd simulation-service
uv sync
DOZERDB_URI=bolt://localhost:7687 uv run uvicorn app.main:app --host 0.0.0.0 --port 5001 --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev   # http://localhost:3000
```

### 4. E2E 테스트

전체 서비스가 떠 있는 상태에서 실행합니다.

```bash
uv run python tests/e2e_simulation_v2.py --gateway http://localhost:4000
```

---

## 환경 변수

루트 `.env`(Gateway와 Simulation Service 공용)

| 변수 | 사용처 | 기본값 |
|---|---|---|
| `LLM_API_KEY` | 공용 | (필수) |
| `LLM_BASE_URL` | 공용 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `LLM_MODEL_NAME` | 공용 | `qwen-plus` |
| `DATABASE_URL` | 공용 | `postgresql://osint:osint_dev@localhost:5432/osint_simulator` |
| `SHADOWBROKER_URL` | 공용 | `http://localhost:8000` |
| `DOZERDB_URI` | Simulation Service | `bolt://dozerdb:7687` |
| `DOZERDB_USER` | Simulation Service | `neo4j` |
| `DOZERDB_PASSWORD` | Simulation Service | `mirofish` |

- Frontend: `GATEWAY_URL`(기본값 `http://localhost:4000`)
- ShadowBroker(`external/Shadowbroker-backend/.env`): `OPENSKY_CLIENT_ID`, `OPENSKY_CLIENT_SECRET`, `AIS_API_KEY`. 비워 두면 해당 데이터 계층이 비어 있습니다.

---

## API

Gateway(`http://localhost:4000`)의 전체 명세는 `/docs`에서 볼 수 있습니다.

| 경로 | 설명 |
|---|---|
| `/api/health` | 헬스 체크(`/detailed`는 ShadowBroker·DB 상태와 서킷 브레이커 포함) |
| `/api/scenario/*` | 시나리오 CRUD, 시드 생성, 시뮬레이션 시작·결정, 진행 상태·체크포인트, What-If, 결과·리포트·GeoJSON, 브리핑, SSE 스트림 |
| `/api/osint/*` | ShadowBroker 프록시, 관측 수집 |
| `/api/geopolitics/*` | 지정학 이벤트 |
| `/api/ontology/*` | 온톨로지 버전 관리 |
| `/api/resolution/*` | 엔티티 해소 검토 대기열과 결정 |
| `/api/causal/*` | 인과 구조 학습, 개입·반사실·기여도 분석 |
| `/api/copilot/*` | AI 코파일럿 |
| `/api/analytics/*` | OSINT 시계열 분석 |
| `/api/actions/*` | 작업 감사 로그 |
| `/api/dashboard/*` | 대시보드 지표 |

Simulation Service는 `/health`만 HTTP로 열고, 명령은 `sim_commands` 채널로 받습니다.

---

## 프로젝트 구조

```
.
├── backend/                    # Gateway API (FastAPI)
│   ├── alembic/                # DB 마이그레이션
│   └── app/
│       ├── causal/             # 인과 DAG, 구조 학습
│       ├── clients/            # ShadowBroker 클라이언트
│       ├── geopolitics/        # 지정학 이벤트 API
│       ├── ontology/           # STIX2 온톨로지, 매핑 규칙, 버전 관리
│       ├── resolution/         # 엔티티 해소
│       ├── routers/            # API 라우터
│       ├── services/           # 시드 생성, 브리핑, 코파일럿, 이벤트 버스 등
│       └── tasks/              # 집계 스케줄러
├── simulation-service/         # LangGraph 시뮬레이션 서비스
│   └── app/
│       ├── engine/             # 결정 엔진(긴장도, 연쇄 반응)
│       ├── graph/              # StateGraph와 노드
│       ├── prompts/            # 에이전트·추출 프롬프트
│       └── services/           # DozerDB 저장, OSINT 주입, GDELT 수집, 명령 수신, 이벤트 발행
├── frontend/                   # Next.js 프론트엔드(지도, OSINT 패널, 시뮬레이션·워룸 UI)
├── external/
│   ├── Shadowbroker-backend/   # OSINT 수집(외부 프로젝트)
│   └── mirofish-backend/       # v11까지 쓰던 MiroFish(현재 미사용)
├── tests/                      # E2E 테스트
├── docs/                       # 버전별 스펙·PRD, 작업 기록
└── docker-compose.yml
```

---

## 버전 이력

| 버전 | 내용 |
|---|---|
| MVP | ShadowBroker·MiroFish 연동, OSINT 기반 시드 생성, 결과 지도 투영 |
| v2 | PostgreSQL + PostGIS, STIX2 2계층 온톨로지, 엔티티 해소, 스키마 버전 관리, 스냅샷 브랜칭, OASIS 지정학 플랫폼 |
| v3 | 지정학 통합, 지능형 시드, 에이전트 웹 검색, 그래프 탭 |
| v4 | 의사결정 포인트, AI 코파일럿, 브리핑·내보내기, 인터랙티브 시뮬레이션, 운영 복원력 |
| v5 | 전체 OSINT 피드 통합, 상황 인식 패널 |
| v6 | 품질·성능 개선, OSINT 시계열 분석 |
| v7 | What-If 반사실 재생 |
| v8 | 인과 DAG, 인과 추론 엔진, 인과 서술 |
| v9 | 인터랙티브 지정학 |
| v10 | 정체성 정리(해상 안보 → 지정학) |
| v11 | 워게임 루프(라운드 단위 외교 시뮬레이션) |
| v12 | MiroFish·OASIS 제거, LangGraph 시뮬레이션 서비스, 지정학 온톨로지, LISTEN/NOTIFY·SSE 통신 |
| v13 | 시뮬레이션 루프 서브그래프 분리, 지정학 이벤트 기반 분석관 개입(HIT) |
| v14 | 파이프라인 단계별 검토 복원 |

상세 스펙과 PRD는 `docs/specs/`, 작업 기록은 `docs/`에 있습니다.

---

## 알려진 한계와 다음 단계

- 온톨로지는 엔티티 17종·관계 15종을 정의했지만, 시뮬레이션 그래프 추출은 엔티티 4종·관계 6종만 씁니다. 그래프에는 타입을 속성(`entity_type`, `fact_type`)으로 저장하고, 정의된 타입으로 검증하지 않습니다.
- OSINT 매핑 규칙(`mapping_rules.py`)과 관계 정의(`edge_types.py`)는 파이프라인에 연결되어 있지 않습니다. 시뮬레이션에는 OSINT가 라운드별 텍스트 요약으로 들어갑니다.
- 해소 엔티티(`stix_objects`)를 적재하는 경로가 없어서, 엔티티 해소 결과와 시드의 근접 관측 근거가 실제로는 비어 있습니다. STIX 검증기에는 v2의 6종만 등록되어 있습니다.
- 관계 이력 테이블(`ontology_edge_history`)은 조회 API만 있고 적재 경로가 없습니다.
- GDELT 분류표 일부가 CAMEO 정의와 다릅니다(12·13을 경제, 14를 군사로 분류).
- PostGIS 관측과 DozerDB 노드를 잇는 공통 키가 없습니다.
- 다음 단계: STIX ID를 두 저장소의 공통 키로 사용, 저장 시점의 타입 검증, 매핑 규칙의 파이프라인 연결

---

## 외부 프로젝트

- **ShadowBroker**: OSINT 수집·지리공간 백엔드(`external/Shadowbroker-backend/`)
- **MiroFish**: v11까지 확장해 쓴 OASIS 기반 멀티 에이전트 엔진(AGPL-3.0). v12에서 제거했고, 소스는 `external/mirofish-backend/`에 참고용으로 남아 있습니다.
- **DozerDB**: Neo4j 호환 그래프 DB
