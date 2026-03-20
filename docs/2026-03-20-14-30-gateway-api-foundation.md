# Gateway API Foundation 구현 (PRD 1)

> 날짜: 2026-03-20
> 프롬프트: "PRD Next - 다음 작업 진행" → PRD 1 (gateway-api-foundation) 선택 → 구현

## 변경 사항

### 생성된 파일

| 파일 | 용도 |
|---|---|
| `backend/pyproject.toml` | Python 프로젝트 설정 + 의존성 (FastAPI, uvicorn, httpx, pydantic, aiosqlite 등) |
| `backend/app/main.py` | FastAPI 앱 + lifespan (DB 초기화) + 라우터 등록 + `/api/health` |
| `backend/app/config.py` | pydantic-settings 기반 환경 설정 (Gateway, SB, MF, LLM, DB 경로) |
| `backend/app/database.py` | aiosqlite SQLite 연결 + 3개 테이블 스키마 (scenarios, seeds, simulation_results) |
| `backend/app/models/scenario.py` | ScenarioCreate, ScenarioResponse, ScenarioCreatedResponse Pydantic 모델 |
| `backend/app/models/seed.py` | SeedMetadata, SeedResponse Pydantic 모델 (기본 구조) |
| `backend/app/models/result.py` | SimulationResultResponse Pydantic 모델 (기본 구조) |
| `backend/app/routers/scenario.py` | 시나리오 CRUD — POST/GET/GET/{id}/DELETE |
| `backend/app/routers/osint.py` | OSINT 프록시 스텁 — 3개 엔드포인트 (501) |
| `backend/app/routers/simulation.py` | 시뮬레이션/시드/결과 스텁 — 7개 엔드포인트 (501) |
| `backend/Dockerfile` | Gateway 컨테이너 빌드 (Python 3.12 + uv) |
| `docker-compose.yml` | SB(8000) + MF(5001) + Gateway(4000) 오케스트레이션 |
| `.env.example` | 환경변수 템플릿 |

### 등록된 API 라우트 (15개)

```
GET     /api/health
GET     /api/osint/live_data                      (501 stub)
GET     /api/osint/live_data/fast                  (501 stub)
GET     /api/osint/live_data/slow                  (501 stub)
GET     /api/scenario                              ✅ 구현
POST    /api/scenario                              ✅ 구현
DELETE  /api/scenario/{scenario_id}                ✅ 구현
GET     /api/scenario/{scenario_id}                ✅ 구현
GET     /api/scenario/{scenario_id}/geojson        (501 stub)
GET     /api/scenario/{scenario_id}/report         (501 stub)
GET     /api/scenario/{scenario_id}/results        (501 stub)
GET     /api/scenario/{scenario_id}/seed           (501 stub)
POST    /api/scenario/{scenario_id}/seed           (501 stub)
POST    /api/scenario/{scenario_id}/simulate       (501 stub)
GET     /api/scenario/{scenario_id}/status         (501 stub)
```

## 검증 결과

- ✅ `uv sync` — 24개 패키지 설치 성공
- ✅ `uv run uvicorn app.main:app --port 4000` — 서버 정상 기동
- ✅ `GET /api/health` → 200 `{"status": "ok"}`
- ✅ 시나리오 CRUD 라이프사이클: POST(201) → GET list → GET/{id} → DELETE(204) → GET(빈 목록)
- ✅ 404 응답: 존재하지 않는 시나리오 조회
- ✅ 501 응답: 미구현 스텁 엔드포인트 10개

## PRD 1 마일스톤 완료 상태

- [x] M1: Python 프로젝트 스켈레톤
- [x] M2: Docker Compose 오케스트레이션 (파일 작성, 실행은 외부 프로젝트 복사 후)
- [x] M3: SQLite + 시나리오 CRUD API
- [x] M4: 라우터 스캐폴딩 (501 stubs)
- [x] M5: 환경 설정 + .env.example

## 다음 단계

PRD 1 완료로 PRD 2 (shadowbroker-integration)와 PRD 6a (frontend-foundation)를 병렬 시작 가능.
