# OSINT Simulator (Ghostfish)

실시간 OSINT 데이터를 시드로 AI 에이전트가 지정학적 시나리오를 시뮬레이션하고 지도 위에 시각화하는 시스템. 코드명 Ghostfish는 두 핵심 외부 서비스인 MiroFish와 ShadowBroker의 합성어다.

---

## 아키텍처 개요

```
Frontend (Next.js 16, :8090)
        |
        v
Gateway API (FastAPI, :4000)
        |
   +---------+-----------+----------+
   |         |           |          |
   v         v           v          v
ShadowBroker  MiroFish  PostgreSQL  DozerDB
  (:8000)    (:5001)    (:5432)   (Neo4j, :7687)
```

---

## 주요 기능

- 실시간 OSINT 데이터 수집 (선박 AIS, 항공기, 위성, GDELT 지정학 이벤트)
- AI 시드 생성 (OSINT 데이터 -> 자연어 시나리오 문서)
- MiroFish 파이프라인 연동 (온톨로지 -> 그래프 -> 에이전트 프로필 -> OASIS 시뮬레이션)
- 지정학 시뮬레이션 (국가 행위자 간 상호작용, 긴장도 분석)
- 인터랙티브 시뮬레이션 (중간 개입, 의사결정 포인트, What-If 분기)
- AI 코파일럿 (시나리오 질의, 컨텍스트 기반 분석)
- 브리핑 생성 (인텔리전스 스타일 보고서)
- 지도 시각화 (MapLibre GL, 시뮬레이션 결과 GeoJSON 오버레이)
- 헬스 대시보드 (서비스 상태, 서킷 브레이커)

---

## 기술 스택

| 영역 | 기술 |
|------|------|
| Backend | Python 3.12, FastAPI, httpx, asyncpg, stix2, OpenAI SDK (OpenAI Compatible API), DuckDuckGo Search |
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS 4, MapLibre GL, D3.js, Recharts |
| Database | PostgreSQL 16 + PostGIS, DozerDB (Neo4j compatible) |
| Infra | Docker Compose, uv (Python), npm (Node.js) |

---

## 빠른 시작

### 사전 요구사항

- Docker, Docker Compose
- uv (Python 패키지 관리)
- Node.js 20+

### 1단계: 환경 설정

```bash
cp .env.example .env
# .env 파일에 LLM_API_KEY 등 설정
```

### 2단계: Docker Compose로 전체 서비스 실행

```bash
docker compose up -d
```

실행되는 서비스:

| 서비스 | 포트 |
|--------|------|
| dozerdb | :7474 (HTTP), :7687 (Bolt) |
| shadowbroker | :8000 |
| mirofish | :5001 |
| postgres | :5432 |
| gateway | :4000 |
| frontend | :8090 |

### 3단계: 로컬 개발 (서비스 별도 실행)

**Backend:**

```bash
cd backend
uv sync
uv run uvicorn app.main:app --host 0.0.0.0 --port 4000 --reload
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev
```

---

## 환경 변수

`.env.example` 참조. 주요 변수:

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `GATEWAY_PORT` | Gateway API 포트 | `4000` |
| `SHADOWBROKER_URL` | ShadowBroker 백엔드 URL | `http://localhost:8000` |
| `MIROFISH_URL` | MiroFish 백엔드 URL | `http://localhost:5001` |
| `LLM_API_KEY` | LLM API 키 (OpenAI Compatible) | - |
| `LLM_BASE_URL` | LLM API Base URL | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `LLM_MODEL_NAME` | LLM 모델명 | `qwen-plus` |
| `DATABASE_URL` | PostgreSQL 연결 문자열 | `postgresql://osint:osint_dev@localhost:5432/osint_simulator` |

---

## 프로젝트 구조

```
osint-simulator/
├── backend/           # Gateway API (FastAPI)
│   ├── app/
│   │   ├── clients/   # ShadowBroker, MiroFish HTTP 클라이언트
│   │   ├── geopolitics/ # 지정학 이벤트 엔진
│   │   ├── models/    # Pydantic 모델
│   │   ├── ontology/  # STIX2 온톨로지
│   │   ├── resolution/ # Entity Resolution
│   │   ├── routers/   # API 라우터
│   │   ├── services/  # 핵심 비즈니스 로직
│   │   └── tasks/     # 백그라운드 태스크
│   └── data/          # 정적 데이터 (군함 DB 등)
├── frontend/          # Next.js 16 프론트엔드
│   └── src/
│       ├── components/
│       │   ├── charts/     # 시계열 차트
│       │   ├── map/        # MapLibre 지도
│       │   ├── osint/      # OSINT 데이터 패널
│       │   └── simulation/ # 시뮬레이션 UI (25+ 컴포넌트)
│       ├── hooks/     # React hooks
│       ├── lib/       # 유틸리티
│       └── types/     # TypeScript 타입
├── external/          # 외부 서비스 소스
│   ├── mirofish-backend/
│   └── Shadowbroker-backend/
├── docs/              # 작업 기록, PRD, 스펙
└── docker-compose.yml
```

---

## API 엔드포인트

Gateway API (`localhost:4000`) 주요 라우트 그룹:

| 경로 | 설명 |
|------|------|
| `/api/health` | 헬스 체크 |
| `/api/scenario/*` | 시나리오 CRUD + 시드 생성 |
| `/api/simulation/*` | 시뮬레이션 실행/조회/제어 |
| `/api/osint/*` | ShadowBroker OSINT 프록시 |
| `/api/geopolitics/*` | 지정학 이벤트 |
| `/api/ontology/*` | 온톨로지 관리 |
| `/api/copilot/*` | AI 코파일럿 |
| `/api/analytics/*` | 분석/통계 |
| `/api/actions/*` | 액션 레이어 |
| `/api/dashboard/*` | 대시보드 메트릭 |

전체 스펙은 서버 실행 후 `http://localhost:4000/docs` (Swagger UI) 참조.

---

## 외부 의존 서비스

**ShadowBroker**
OSINT 데이터 수집 및 지리공간 시각화 백엔드. AIS 선박, 항공기, 위성, GDELT 이벤트 등 20개 이상의 피드를 제공한다. 소스: `external/Shadowbroker-backend/`.

**MiroFish**
멀티 에이전트 시뮬레이션 및 예측 엔진. OASIS 프레임워크 기반으로 에이전트 프로필 생성부터 시뮬레이션 실행까지 파이프라인을 담당한다. 소스: `external/mirofish-backend/`.

**DozerDB**
Neo4j 호환 그래프 데이터베이스. 엔티티 관계 그래프를 저장하며 온톨로지 및 시뮬레이션 결과 연결에 사용된다.
