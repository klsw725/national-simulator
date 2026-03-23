# PRD: Gateway API Foundation

> Status: Complete
> Created: 2026-03-20
> Dependencies: 없음 (첫 번째 PRD)
> 관련 스펙: `specs/MVP-SPEC.md` Section 2, 6, 7, 8

---

## 1. 문제 정의

OSINT Simulator 프로젝트는 ShadowBroker(OSINT 데이터 수집)와 MiroFish(AI 시뮬레이션)를 연결하는 게이트웨이가 필요하다. 현재 프로젝트에는 스펙(MVP-SPEC.md)과 가이드라인(AGENTS.md)만 존재하며, 실행 가능한 코드 인프라가 전무하다.

두 소스 프로젝트를 수정하지 않고 HTTP API로만 연동해야 하므로, 중간에서 요청을 조율하고 결과를 저장하는 게이트웨이 레이어가 필수적이다.

## 2. 솔루션 개요

- **FastAPI 기반 게이트웨이 API** (port 4000) — 시나리오 관리, 시뮬레이션 조율, OSINT 프록시
- **Docker Compose** — ShadowBroker(8000) + MiroFish(5001) + Gateway(4000) 멀티서비스 오케스트레이션
- **SQLite** — 시나리오, 시드 문서, 시뮬레이션 결과의 영속 저장
- **uv** — Python 패키지 관리 (pip 사용 금지)

## 3. 기술 상세

### 3.1 프로젝트 구조

```
osint-simulator/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI 앱 + 라우터 등록
│   │   ├── config.py            # 환경 설정 (pydantic-settings)
│   │   ├── database.py          # SQLite 연결 + 테이블 생성
│   │   ├── clients/             # 외부 API 클라이언트 (PRD 2, 4에서 구현)
│   │   ├── services/            # 비즈니스 로직 (PRD 3, 4, 5에서 구현)
│   │   ├── models/              # Pydantic 모델
│   │   │   ├── scenario.py
│   │   │   ├── seed.py
│   │   │   └── result.py
│   │   ├── routers/             # API 라우터
│   │   │   ├── scenario.py      # /api/scenario/*
│   │   │   ├── osint.py         # /api/osint/* (PRD 2에서 구현)
│   │   │   └── simulation.py    # /api/scenario/{id}/simulate 등
│   │   └── data/                # 정적 데이터 (PRD 3에서 추가)
│   ├── pyproject.toml
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
└── ...
```

### 3.2 핵심 의존성

```toml
[project]
name = "osint-simulator"
version = "0.1.0"
requires-python = ">=3.11"

dependencies = [
    "fastapi>=0.115.0",
    "uvicorn>=0.34.0",
    "httpx>=0.28.0",
    "pydantic>=2.0.0",
    "python-dotenv>=1.0.0",
    "openai>=1.0.0",
    "aiosqlite>=0.21.0",
]
```

### 3.3 Gateway API 라우트 (전체)

```
시나리오 관리
  POST   /api/scenario                  시나리오 생성
  GET    /api/scenario                  시나리오 목록
  GET    /api/scenario/{id}             시나리오 상세
  DELETE /api/scenario/{id}             시나리오 삭제

시드 생성 (PRD 3에서 구현체 연결)
  POST   /api/scenario/{id}/seed        시드 문서 생성
  GET    /api/scenario/{id}/seed        시드 문서 조회

시뮬레이션 (PRD 4에서 구현체 연결)
  POST   /api/scenario/{id}/simulate    시뮬레이션 시작
  GET    /api/scenario/{id}/status      시뮬레이션 상태
  GET    /api/scenario/{id}/results     시뮬레이션 결과

결과 시각화 (PRD 5에서 구현체 연결)
  GET    /api/scenario/{id}/geojson     GeoJSON 결과
  GET    /api/scenario/{id}/report      예측 보고서

OSINT 프록시 (PRD 2에서 구현체 연결)
  GET    /api/osint/live_data           SB 전체 데이터
  GET    /api/osint/live_data/fast      SB 빠른 갱신 데이터
  GET    /api/osint/live_data/slow      SB 느린 갱신 데이터

헬스체크
  GET    /api/health                    게이트웨이 상태
```

> **주의**: API 경로는 `snake_case` (MiroFish 관례, AGENTS.md 규칙)

### 3.4 SQLite 스키마

```sql
CREATE TABLE scenarios (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    region_bbox TEXT NOT NULL,        -- JSON: [minLng, minLat, maxLng, maxLat]
    region_name TEXT NOT NULL,
    question TEXT NOT NULL,
    max_rounds INTEGER DEFAULT 10,
    data_sources TEXT NOT NULL,       -- JSON: ["ships", "geopolitics"]
    status TEXT DEFAULT 'created',    -- created | seeding | simulating | completed | failed
    seed_status TEXT DEFAULT 'pending',
    simulation_status TEXT DEFAULT 'pending',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE seeds (
    id TEXT PRIMARY KEY,
    scenario_id TEXT NOT NULL REFERENCES scenarios(id),
    text TEXT NOT NULL,               -- 마크다운 시드 문서
    metadata TEXT NOT NULL,           -- JSON: {vessels_count, actors_identified, ...}
    created_at TEXT NOT NULL
);

CREATE TABLE simulation_results (
    id TEXT PRIMARY KEY,
    scenario_id TEXT NOT NULL REFERENCES scenarios(id),
    mirofish_simulation_id TEXT,      -- MiroFish 내부 simulation_id
    mirofish_project_id TEXT,         -- MiroFish 내부 project_id
    status TEXT DEFAULT 'pending',    -- pending | running | completed | failed
    platform TEXT DEFAULT 'twitter',
    results TEXT,                     -- JSON: 시뮬레이션 결과 전체
    geojson TEXT,                     -- JSON: GeoJSON FeatureCollection
    report TEXT,                      -- 마크다운 보고서
    created_at TEXT NOT NULL,
    completed_at TEXT
);
```

### 3.5 환경변수

```env
# Gateway
GATEWAY_PORT=4000

# 소스 프로젝트 연결
SHADOWBROKER_URL=http://localhost:8000
MIROFISH_URL=http://localhost:5001

# LLM (시드 문서 생성용)
LLM_API_KEY=
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL_NAME=qwen-plus
```

### 3.6 Docker Compose

```yaml
services:
  shadowbroker:
    build:
      context: ../Shadowbroker/backend
    ports: ["8000:8000"]
    env_file: ../Shadowbroker/backend/.env

  mirofish:
    build:
      context: ../mirofish-ko/backend
    command: uv run python run.py
    ports: ["5001:5001"]
    env_file: ../mirofish-ko/backend/.env

  gateway:
    build: ./backend
    ports: ["4000:4000"]
    env_file: .env
    depends_on: [shadowbroker, mirofish]
```

## 4. 마일스톤

- [x] **M1: Python 프로젝트 스켈레톤** — `backend/` 디렉토리 구조, `pyproject.toml`, `app/main.py`, `app/config.py` 생성. `uv sync`로 의존성 설치 확인. `uv run uvicorn app.main:app`으로 서버 기동 확인.
  - 검증: `curl localhost:4000/api/health` → 200 응답

- [x] **M2: Docker Compose 오케스트레이션** — `docker-compose.yml` 작성. ShadowBroker(8000), MiroFish(5001), Gateway(4000) 3개 서비스 동시 기동.
  - 검증: `docker compose up` → 3개 서비스 모두 healthy 상태

- [x] **M3: SQLite + 시나리오 CRUD API** — `database.py`로 SQLite 테이블 생성. 시나리오 생성/목록/상세/삭제 API 구현. Pydantic 모델로 요청/응답 검증.
  - 검증: POST → GET → DELETE 시나리오 라이프사이클 동작

- [x] **M4: 라우터 스캐폴딩** — 시드/시뮬레이션/결과/OSINT 라우터의 빈 엔드포인트 등록. 각 라우터는 501 Not Implemented 응답 반환 (후속 PRD에서 구현체 연결).
  - 검증: 모든 라우트가 등록되고 501 응답 반환

- [x] **M5: 환경 설정 + .env.example** — pydantic-settings 기반 Config 클래스. `.env.example` 파일 작성. SB_URL, MF_URL, LLM 설정 로드 확인.
  - 검증: 환경변수 누락 시 명확한 에러 메시지 출력

## 5. 성공 기준

- `uv run uvicorn app.main:app`으로 게이트웨이가 정상 기동된다
- Docker Compose로 3개 서비스가 동시에 기동된다
- 시나리오 CRUD API가 SQLite에 영속 저장/조회된다
- 모든 API 라우트가 등록되어 있다 (구현체는 후속 PRD)
- 환경 설정이 `.env` 파일에서 로드된다

## 6. 위험 및 완화

| 위험 | 완화 |
|------|------|
| ShadowBroker/MiroFish Docker 빌드 실패 | 로컬 직접 실행 모드도 지원 (Docker 없이 개별 서비스 기동) |
| SQLite 동시성 제약 | MVP 수준에서는 단일 프로세스로 충분. 동시성 문제 발생 시 WAL 모드 활성화 |
| 포트 충돌 | 환경변수로 포트 설정 가능하게 구현 |

## 7. 참고

### 관련 PRD
- **PRD 2 (shadowbroker-integration)** — OSINT 프록시 엔드포인트 구현체
- **PRD 3 (seed-generation)** — 시드 생성 엔드포인트 구현체
- **PRD 4 (simulation-orchestration)** — 시뮬레이션 엔드포인트 구현체
- **PRD 5 (result-projection)** — 결과/GeoJSON/보고서 엔드포인트 구현체

### 소스 프로젝트
- ShadowBroker: `/home/swlee/Shadowbroker` (대문자 S 주의)
- MiroFish: `/home/swlee/mirofish-ko`

## 진행 로그

| 날짜 | 상태 | 내용 |
|------|------|------|
| 2026-03-20 | Draft | PRD 초안 작성 |
