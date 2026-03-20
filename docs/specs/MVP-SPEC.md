# OSINT Simulator MVP - Technical Specification

> Version: 0.1.0
> Date: 2026-03-20
> Status: Draft
> Codename: **Ghostfish** (MiroFish + ShadowBroker)

---

## 1. Executive Summary

실시간 OSINT 데이터를 시드로 투입하여 AI 에이전트가 지정학적 시나리오를 시뮬레이션하고, 그 결과를 지도 위에 시각화하는 시스템.

**핵심 가치 제안**: "이 해역에 이런 군함들이 배치된 상황에서, 관련 국가들은 어떻게 반응하는가?"

### 소스 프로젝트

| 프로젝트 | 역할 | 경로 |
|---|---|---|
| **ShadowBroker** | OSINT 데이터 수집 / 지리공간 시각화 | `/home/swlee/Shadowbroker` |
| **MiroFish** | 멀티 에이전트 시뮬레이션 / 예측 엔진 | `/home/swlee/mirofish-ko` |

### MVP 시나리오: 해상 긴장 시뮬레이션

1. ShadowBroker AIS 피드에서 특정 해역의 군함 데이터를 수집
2. 군함을 국가 행위자로 매핑하여 시드 문서 자동 생성
3. MiroFish 파이프라인으로 온톨로지 생성 → 에이전트 프로필 생성 → OASIS 시뮬레이션
4. 시뮬레이션 결과를 ShadowBroker 지도 위에 오버레이

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────┐
│  FRONTEND (ShadowBroker Next.js + 시뮬레이션 패널)       │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ OSINT 지도     │  │ 시뮬레이션    │  │ 예측 보고서    │  │
│  │ (SB 기존)     │  │ 컨트롤 패널   │  │ (결과 뷰)     │  │
│  └──────┬───────┘  └──────┬───────┘  └───────┬───────┘  │
│         └─────────────────┼──────────────────┘          │
│                           │                              │
├───────────────────────────┼──────────────────────────────┤
│  GATEWAY API (FastAPI)    │                              │
│  ┌────────────────────────┼───────────────────────────┐  │
│  │  /api/osint/*          │  ShadowBroker 프록시       │  │
│  │  /api/simulation/*     │  시뮬레이션 관리            │  │
│  │  /api/scenario/*       │  시나리오 생성/조회         │  │
│  └────────────────────────┴───────────────────────────┘  │
│                                                          │
├──────────────────────────────────────────────────────────┤
│  SERVICES                                                │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ Seed          │  │ MiroFish     │  │ Result        │  │
│  │ Generator     │  │ Pipeline     │  │ Projector     │  │
│  │ (OSINT→시드)  │  │ (기존 코드)   │  │ (결과→지도)   │  │
│  └──────────────┘  └──────────────┘  └───────────────┘  │
│                                                          │
├──────────────────────────────────────────────────────────┤
│  DATA                                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ ShadowBroker  │  │ MiroFish     │  │ Simulation    │  │
│  │ Backend       │  │ Graph Store  │  │ Results DB    │  │
│  │ (기존, 8000)  │  │ (Neo4j/Zep)  │  │ (SQLite)      │  │
│  └──────────────┘  └──────────────┘  └───────────────┘  │
└──────────────────────────────────────────────────────────┘
```

### 설계 원칙

1. **기존 코드 최대 활용** — ShadowBroker와 MiroFish를 수정하지 않고, 새 프로젝트가 양쪽을 호출
2. **OASIS 무수정** — 지정학적 상호작용을 소셜미디어 메타포로 매핑
3. **최소 인프라** — MVP에서는 PostgreSQL, Entity Resolution, Action Layer 불필요
4. **느슨한 결합** — 각 서비스는 독립적으로 실행 가능

---

## 3. Components

### 3.1 신규 구축 (4개)

#### 3.1.1 Seed Generator

OSINT 데이터를 MiroFish가 이해하는 자연어 시드 문서로 변환한다.

**입력**: ShadowBroker API의 선박/항공기/분쟁 데이터 + 사용자 지정 해역/시나리오
**출력**: MiroFish 시드 문서 (마크다운 텍스트)

```python
# 핵심 인터페이스
class SeedGenerator:
    def __init__(self, sb_client: ShadowBrokerClient):
        self.sb = sb_client

    async def generate(self, scenario: ScenarioConfig) -> SeedDocument:
        """
        1. ShadowBroker API에서 해당 해역의 데이터 조회
        2. 군함을 국가 행위자로 매핑
        3. GDELT 분쟁 이벤트 조회
        4. 자연어 시드 문서 생성 (LLM 사용)
        """
        pass
```

**세부 요구사항**:
- ShadowBroker `/api/ships` 엔드포인트에서 선박 데이터 조회
- `ship_type` 기반 군함 필터링 (carrier, destroyer, frigate 등)
- 선박의 `flag` 필드로 국가 행위자 매핑
- GDELT `/api/geopolitics` 데이터로 지역 긴장도 컨텍스트 추가
- 출력은 MiroFish가 기대하는 시드 텍스트 형식 (마크다운)

#### 3.1.2 ShadowBroker Client

ShadowBroker 백엔드 API를 호출하는 클라이언트.

```python
class ShadowBrokerClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url

    async def get_ships(self, bbox: BBox = None) -> list[dict]:
        """GET /api/ships — AIS 선박 데이터"""
        pass

    async def get_flights(self, bbox: BBox = None) -> list[dict]:
        """GET /api/flights — 항공기 데이터"""
        pass

    async def get_geopolitics(self) -> list[dict]:
        """GET /api/geopolitics — GDELT 분쟁 이벤트"""
        pass

    async def get_carriers(self) -> list[dict]:
        """GET /api/ships (type=carrier) — 항모 위치"""
        pass
```

#### 3.1.3 MiroFish Pipeline Adapter

MiroFish의 기존 파이프라인을 프로그래밍 방식으로 호출하는 어댑터.

```python
class MiroFishAdapter:
    def __init__(self, mirofish_url: str = "http://localhost:5001"):
        self.url = mirofish_url

    async def generate_ontology(
        self, seed_text: str, simulation_requirement: str
    ) -> dict:
        """POST /api/ontology/generate"""
        pass

    async def build_graph(self, project_id: str) -> str:
        """POST /api/graph/build → task_id"""
        pass

    async def generate_profiles(
        self, graph_id: str, platform: str = "twitter"
    ) -> list[dict]:
        """POST /api/profiles/generate"""
        pass

    async def run_simulation(
        self, graph_id: str, config: SimulationConfig
    ) -> str:
        """POST /api/simulation/run → simulation_id"""
        pass

    async def get_simulation_status(self, simulation_id: str) -> dict:
        """GET /api/simulation/{id}/status"""
        pass

    async def get_simulation_results(self, simulation_id: str) -> dict:
        """GET /api/simulation/{id}/results"""
        pass
```

#### 3.1.4 Result Projector

시뮬레이션 결과를 지도 시각화용 GeoJSON으로 변환한다.

```python
class ResultProjector:
    def project_to_geojson(
        self, simulation_results: dict, entity_locations: dict
    ) -> dict:
        """
        시뮬레이션 결과를 GeoJSON FeatureCollection으로 변환.

        각 에이전트(국가 행위자)에 대해:
        - 위치 (수도 또는 군함 위치)
        - 긴장 수준 (시뮬레이션 포스트의 감정 분석)
        - 주요 발언 요약
        - 동맹/적대 관계 라인
        """
        pass
```

### 3.2 기존 코드 활용 (수정 없이 호출)

| 모듈 | 소스 프로젝트 | 호출 방식 |
|---|---|---|
| AIS 선박 데이터 수집 | ShadowBroker `services/ais_stream.py` | HTTP API (`/api/ships`) |
| GDELT 분쟁 이벤트 | ShadowBroker `services/geopolitics.py` | HTTP API (`/api/geopolitics`) |
| 항모 위치 추적 | ShadowBroker `services/carrier_tracker.py` | HTTP API (`/api/ships`) |
| MapLibre 지도 렌더링 | ShadowBroker `frontend/` | 프론트엔드 확장 |
| 온톨로지 생성 | MiroFish `ontology_generator.py` | HTTP API (`/api/ontology/generate`) |
| 그래프 구축 | MiroFish `graph_builder.py` | HTTP API (`/api/graph/build`) |
| 에이전트 프로필 생성 | MiroFish `oasis_profile_generator.py` | HTTP API (`/api/profiles/generate`) |
| OASIS 시뮬레이션 실행 | MiroFish `simulation_runner.py` | HTTP API (`/api/simulation/run`) |
| 예측 보고서 생성 | MiroFish `report_agent.py` | HTTP API (`/api/report/generate`) |

---

## 4. Data Flow (상세)

### Phase 1: 시나리오 생성

```
사용자 입력:
  - 관심 해역 (bbox 또는 지역명)
  - 시뮬레이션 질문 ("미중 해군 대치 시 일본은 어떻게 반응하는가?")
  - 라운드 수 (기본값: 10)
         │
         ▼
[Seed Generator]
  1. SB API 호출: GET /api/ships?bbox=...
     → 해당 해역의 군함 목록 수신
     → 예: [{mmsi: "...", name: "USS Gerald Ford", flag: "US",
             type: "carrier", lat: 15.2, lng: 115.8}, ...]

  2. 군함 → 국가 매핑:
     → military_vessel_db.json (공개 군함 데이터베이스)
     → flag 필드 기반 국가 식별
     → 결과: {US: [carrier, destroyer x2], CN: [destroyer x3, frigate x2]}

  3. SB API 호출: GET /api/geopolitics
     → 해당 해역 근처 GDELT 이벤트 필터링
     → 긴장도 컨텍스트 추출

  4. LLM으로 시드 문서 생성:
     → 프롬프트: 군함 배치 현황 + GDELT 컨텍스트 + 사용자 질문
     → 출력: 마크다운 시드 문서 (~2000자)
         │
         ▼
[SeedDocument]
  "## 현재 상황 요약
   남중국해 서사군도 인근에서 미국 항공모함 전단과
   중국 해군 구축함 편대가 근접 기동 중이다.
   USS Gerald Ford(CVN-78)를 중심으로 한 미국 항모전단은...
   중국 인민해방군 해군의 052D형 구축함 3척이...
   GDELT 데이터에 따르면 최근 48시간 내 양국 간
   외교적 긴장이 Goldstein Scale -5.2로 기록되었으며..."
```

### Phase 2: MiroFish 파이프라인 실행

```
[SeedDocument] → MiroFish API
         │
         ▼
POST /api/ontology/generate
  body: {
    files: [seed_document.md],
    simulation_requirement: "미중 해군 대치 시 주변국 반응 시뮬레이션"
  }
  → ontology: {
      entity_types: [
        {name: "Superpower", description: "Major military power with global reach"},
        {name: "RegionalPower", description: "Regional military power"},
        {name: "MilitaryAlliance", description: "Military alliance organization"},
        {name: "NavalFleet", description: "Naval fleet or carrier group"},
        ...
        {name: "Person", ...},
        {name: "Organization", ...}
      ],
      edge_types: [
        {name: "ALLIED_WITH", ...},
        {name: "HOSTILE_TO", ...},
        {name: "COMMANDS", ...},
        ...
      ]
    }
         │
         ▼
POST /api/graph/build
  → graph_id: "mirofish_abc123"
  → 엔티티 추출: US, China, Japan, Philippines, Taiwan, ...
  → 관계 추출: US-ALLIED_WITH-Japan, US-HOSTILE_TO-China, ...
         │
         ▼
POST /api/profiles/generate
  body: {graph_id, platform: "twitter"}
  → 에이전트 프로필 생성:
    - "United States": persona="세계 최강 해군력을 보유한 초강대국..."
    - "China": persona="급성장하는 해양 강국. 남중국해에 대한..."
    - "Japan": persona="미일동맹의 핵심 파트너. 헌법 9조의 제약..."
    - "Philippines": persona="남중국해 영유권 분쟁의 당사국..."
         │
         ▼
POST /api/simulation/run
  body: {
    graph_id,
    platform: "twitter",
    max_rounds: 10,
    requirement: "미중 해군 대치 시 주변국의 외교적 반응을 시뮬레이션"
  }
  → simulation_id: "sim_xyz789"
  → OASIS Twitter 시뮬레이션 실행 (기존 로직 그대로)
```

### Phase 3: 결과 시각화

```
GET /api/simulation/sim_xyz789/results
  → {
      rounds: [
        {round: 1, posts: [
          {agent: "United States", action: "CREATE_POST",
           content: "항행의 자유 작전을 지속할 것임을 재확인한다"},
          {agent: "China", action: "QUOTE_POST",
           content: "내정 간섭에 강력히 반대한다"},
          {agent: "Japan", action: "REPOST", target: "United States"},
          ...
        ]},
        ...
      ],
      summary: "시뮬레이션 결과 분석..."
    }
         │
         ▼
[Result Projector]
  → GeoJSON FeatureCollection:
    {
      type: "FeatureCollection",
      features: [
        {
          type: "Feature",
          geometry: {type: "Point", coordinates: [126.9780, 37.5665]},
          properties: {
            actor: "South Korea",
            tension_level: 0.6,
            stance: "cautious_ally",
            key_statement: "동맹 의무와 경제적 관계 사이 균형...",
            post_count: 3,
            repost_count: 1
          }
        },
        ...
      ]
    }
         │
         ▼
[ShadowBroker MapLibre]
  → 시뮬레이션 결과 레이어 오버레이
  → 국가별 긴장 수준 히트맵
  → 동맹/적대 관계 라인
  → 사이드 패널: 시뮬레이션 타임라인
```

---

## 5. Data Models

### 5.1 ScenarioConfig

```typescript
interface ScenarioConfig {
  id: string;                    // UUID
  name: string;                  // 시나리오 이름
  region: {
    bbox: [number, number, number, number];  // [minLng, minLat, maxLng, maxLat]
    name: string;                // "South China Sea"
  };
  question: string;              // 시뮬레이션 질문
  max_rounds: number;            // OASIS 시뮬레이션 라운드 수
  data_sources: string[];        // ["ships", "flights", "geopolitics"]
  created_at: string;            // ISO 8601
}
```

### 5.2 SeedDocument

```typescript
interface SeedDocument {
  scenario_id: string;
  text: string;                  // 마크다운 시드 문서
  metadata: {
    vessels_count: number;       // 감지된 군함 수
    actors_identified: string[]; // 식별된 국가 행위자
    gdelt_events_count: number;  // GDELT 이벤트 수
    tension_score: number;       // 전체 긴장도 (0-10)
    data_timestamp: string;      // 데이터 수집 시각
  };
}
```

### 5.3 SimulationResult

```typescript
interface SimulationResult {
  simulation_id: string;
  scenario_id: string;
  status: "running" | "completed" | "failed";
  platform: "twitter";
  rounds: Round[];
  summary: string;               // LLM 생성 요약
  report: string;                // MiroFish 보고서
  geojson: GeoJSON.FeatureCollection;  // 지도 시각화용
  created_at: string;
  completed_at: string;
}

interface Round {
  round_number: number;
  posts: Post[];
  timestamp: string;
}

interface Post {
  agent_name: string;            // 국가/행위자 이름
  action: string;                // CREATE_POST, QUOTE_POST, REPOST, ...
  content: string;               // 발언 내용
  target_post_id?: string;       // QUOTE/REPOST 대상
  sentiment: number;             // -1.0 ~ 1.0
}
```

### 5.4 Military Vessel Mapping

```typescript
// military_vessels.json — 공개 군함 데이터베이스 (정적 파일)
interface MilitaryVessel {
  mmsi: string;
  imo: string;
  name: string;
  hull_number: string;           // "CVN-78"
  class: string;                 // "Gerald R. Ford-class"
  type: string;                  // "carrier" | "destroyer" | "frigate" | ...
  country: string;               // "US" | "CN" | "RU" | ...
  navy: string;                  // "United States Navy"
  status: string;                // "active" | "reserve"
}
```

### 5.5 Actor GeoJSON (시각화)

```typescript
interface ActorFeature {
  type: "Feature";
  geometry: {
    type: "Point";
    coordinates: [number, number];  // [lng, lat]
  };
  properties: {
    actor: string;               // 국가/행위자 이름
    actor_type: string;          // "superpower" | "regional_power" | ...
    tension_level: number;       // 0.0 ~ 1.0
    stance: string;              // "supportive" | "opposing" | "neutral" | ...
    key_statement: string;       // 핵심 발언 요약
    post_count: number;          // 총 발언 수
    sentiment_avg: number;       // 평균 감정 (-1.0 ~ 1.0)
    color: string;               // 시각화 색상 (#ff0000)
  };
}
```

---

## 6. API Design

### 6.1 Gateway API (신규 — FastAPI, port 4000)

```
시나리오 관리
  POST   /api/scenario                  시나리오 생성
  GET    /api/scenario                  시나리오 목록
  GET    /api/scenario/{id}             시나리오 상세
  DELETE /api/scenario/{id}             시나리오 삭제

시드 생성
  POST   /api/scenario/{id}/seed        시드 문서 생성
  GET    /api/scenario/{id}/seed        시드 문서 조회

시뮬레이션
  POST   /api/scenario/{id}/simulate    시뮬레이션 시작
  GET    /api/scenario/{id}/status      시뮬레이션 상태
  GET    /api/scenario/{id}/results     시뮬레이션 결과
  GET    /api/scenario/{id}/geojson     GeoJSON 결과 (지도용)
  GET    /api/scenario/{id}/report      예측 보고서

OSINT 프록시 (ShadowBroker 포워딩)
  GET    /api/osint/ships               선박 데이터
  GET    /api/osint/flights             항공기 데이터
  GET    /api/osint/geopolitics         분쟁 이벤트
  GET    /api/osint/carriers            항모 위치
```

### 6.2 시나리오 생성 요청/응답 예시

```json
// POST /api/scenario
// Request
{
  "name": "남중국해 미중 대치 시나리오",
  "region": {
    "bbox": [108.0, 5.0, 121.0, 23.0],
    "name": "South China Sea"
  },
  "question": "미중 해군 대치 시 일본, 한국, 필리핀은 어떻게 반응하는가?",
  "max_rounds": 10,
  "data_sources": ["ships", "geopolitics"]
}

// Response
{
  "id": "scn_abc123",
  "status": "created",
  "seed_status": "pending",
  "simulation_status": "pending"
}
```

### 6.3 시드 생성 요청/응답 예시

```json
// POST /api/scenario/scn_abc123/seed
// Response
{
  "scenario_id": "scn_abc123",
  "seed_status": "completed",
  "metadata": {
    "vessels_count": 12,
    "actors_identified": ["US", "CN", "JP", "PH", "TW", "KR"],
    "gdelt_events_count": 8,
    "tension_score": 7.2,
    "data_timestamp": "2026-03-20T14:30:00Z"
  },
  "preview": "## 현재 상황 요약\n남중국해 서사군도 인근에서..."
}
```

---

## 7. Tech Stack

### 백엔드

| 기술 | 용도 | 이유 |
|---|---|---|
| **Python 3.12** | 백엔드 전체 | MiroFish/ShadowBroker 호환 |
| **FastAPI** | Gateway API | ShadowBroker와 동일, 비동기 지원 |
| **httpx** | HTTP 클라이언트 | SB/MF API 호출용, 비동기 지원 |
| **uvicorn** | ASGI 서버 | FastAPI 표준 |

### 프론트엔드

| 기술 | 용도 | 이유 |
|---|---|---|
| **Next.js 16** | ShadowBroker 프론트엔드 확장 | 기존 코드 활용 |
| **MapLibre GL** | 지도 렌더링 | 기존 코드 활용 |
| **React 19** | UI 컴포넌트 | ShadowBroker와 동일 |
| **TypeScript** | 타입 안전성 | ShadowBroker와 동일 |

### 데이터

| 기술 | 용도 | 이유 |
|---|---|---|
| **SQLite** | 시나리오/결과 저장 | MVP에 충분, 설치 불필요 |
| **Neo4j/Zep** | 지식 그래프 | MiroFish 기존 코드 그대로 활용 |

### 인프라

| 기술 | 용도 | 이유 |
|---|---|---|
| **Docker Compose** | 멀티 서비스 오케스트레이션 | SB(8000) + MF(5001) + Gateway(4000) + Frontend(3000) |

---

## 8. Project Structure

```
osint-simulator/
├── specs/
│   └── MVP-SPEC.md              # 이 문서
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI 앱 + Gateway API
│   │   ├── config.py            # 환경 설정
│   │   ├── clients/
│   │   │   ├── shadowbroker.py  # ShadowBroker API 클라이언트
│   │   │   └── mirofish.py      # MiroFish API 클라이언트
│   │   ├── services/
│   │   │   ├── seed_generator.py    # OSINT→시드 문서 변환
│   │   │   ├── vessel_mapper.py     # 군함→국가 매핑
│   │   │   ├── scenario_manager.py  # 시나리오 CRUD
│   │   │   ├── simulation_orchestrator.py  # 파이프라인 오케스트레이션
│   │   │   └── result_projector.py  # 결과→GeoJSON 변환
│   │   ├── models/
│   │   │   ├── scenario.py      # ScenarioConfig 모델
│   │   │   ├── seed.py          # SeedDocument 모델
│   │   │   └── result.py        # SimulationResult 모델
│   │   └── data/
│   │       └── military_vessels.json  # 군함 데이터베이스
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   └── (ShadowBroker frontend을 확장 — 별도 상세 설계)
├── docker-compose.yml           # 전체 서비스 오케스트레이션
├── .env.example
├── .gitignore
└── README.md
```

---

## 9. Environment Variables

```env
# Gateway API
GATEWAY_PORT=4000

# ShadowBroker 연결
SHADOWBROKER_URL=http://localhost:8000

# MiroFish 연결
MIROFISH_URL=http://localhost:5001

# LLM (시드 문서 생성용 — MiroFish와 동일한 키 공유 가능)
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL_NAME=qwen-plus

# MiroFish Graph Store (MiroFish .env에서 복사)
USE_LOCAL_GRAPH=false
ZEP_API_KEY=your_zep_api_key
# 또는
# USE_LOCAL_GRAPH=true
# DOZERDB_URI=bolt://localhost:7687
```

---

## 10. Dependencies

### Python (backend/pyproject.toml)

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
]
```

### 외부 서비스 (Docker Compose로 실행)

```yaml
services:
  shadowbroker:
    # ShadowBroker 백엔드 (port 8000)
    build: ../Shadowbroker/backend
    ports: ["8000:8000"]

  mirofish:
    # MiroFish 백엔드 (port 5001)
    build: ../mirofish-ko/backend
    command: uv run python run.py
    ports: ["5001:5001"]

  gateway:
    # OSINT Simulator Gateway (port 4000)
    build: ./backend
    ports: ["4000:4000"]
    depends_on: [shadowbroker, mirofish]

  frontend:
    # ShadowBroker 프론트엔드 확장 (port 3000)
    build: ./frontend
    ports: ["3000:3000"]
    depends_on: [gateway]
```

---

## 11. MiroFish 프롬프트 커스터마이징

### 온톨로지 생성 프롬프트 가이드

MiroFish의 `ontology_generator.py`는 시드 문서와 `simulation_requirement`를 받아 온톨로지를 자동 생성한다.
MVP에서는 `simulation_requirement`를 지정학 도메인에 맞게 전달한다:

```python
simulation_requirement = """
해상 안보 시나리오의 지정학적 시뮬레이션입니다.

이 시뮬레이션에서:
- 각 엔티티는 국제 무대에서 성명을 발표하고, 외교적 반응을 보이며,
  동맹/적대 관계에 따라 행동하는 '국가 행위자' 또는 '국제 기구'입니다.
- 엔티티 간에는 동맹 지지, 비난 성명, 중립 선언 등의 상호작용을 합니다.
- 우리는 해상 긴장 상황에서 각 행위자의 반응과 여론 전파 경로를
  시뮬레이션해야 합니다.

가능한 엔티티 유형:
- Superpower (초강대국)
- RegionalPower (지역 강국)
- SmallState (소국)
- MilitaryAlliance (군사 동맹, 예: NATO, QUAD)
- InternationalOrganization (국제 기구, 예: UN, ASEAN)
- MediaOutlet (미디어 기관)
- MilitaryCommander (군 지휘관)
- Diplomat (외교관)
- Person (범용 개인)
- Organization (범용 조직)
"""
```

### OASIS 액션 → 지정학 행동 매핑 문서

시뮬레이션 프롬프트에 포함시켜 에이전트가 올바르게 행동하도록 유도:

```python
action_mapping_prompt = """
당신은 소셜미디어 플랫폼에서 국가/기관의 공식 계정을 운영합니다.
각 행동의 의미:

- 포스트 작성 (CREATE_POST): 공식 성명 또는 입장 발표
- 인용 포스트 (QUOTE_POST): 타국 성명에 대한 공식 반응/논평
- 리포스트 (REPOST): 동맹국 성명 지지/전파
- 좋아요 (LIKE_POST): 타국 성명에 대한 암묵적 동의
- 팔로우 (FOLLOW): 외교적 관계 형성 의사 표시
- 아무것도 안 함 (DO_NOTHING): 전략적 관망/무반응
"""
```

---

## 12. Timeline

| 주차 | 마일스톤 | 산출물 |
|---|---|---|
| **W1** | 프로젝트 셋업 + SB 클라이언트 | Docker Compose 기동, SB API 호출 확인 |
| **W2** | 군함 매핑 + 시드 생성기 | 실제 AIS 데이터로 시드 문서 생성 |
| **W3** | MiroFish 어댑터 + 파이프라인 | 시드 → 온톨로지 → 그래프 → 프로필 → 시뮬레이션 |
| **W4** | 결과 프로젝터 + API 통합 | Gateway API 전체 플로우 동작 |
| **W5-6** | 프론트엔드 시각화 | 지도 위 시뮬레이션 결과 오버레이 |
| **W7** | 통합 테스트 + 데모 준비 | 남중국해 시나리오 E2E 데모 |

---

## 13. Success Criteria

MVP 완료의 정의:

- [ ] ShadowBroker에서 실시간 선박 데이터를 수집하여 시드 문서를 자동 생성할 수 있다
- [ ] 시드 문서로부터 MiroFish 파이프라인이 온톨로지 → 그래프 → 프로필 → 시뮬레이션을 완료한다
- [ ] 시뮬레이션 결과가 GeoJSON으로 변환되어 지도 위에 표시된다
- [ ] 최소 1개 시나리오(남중국해)를 처음부터 끝까지 실행할 수 있다
- [ ] 전체 프로세스가 사용자 개입 없이 자동으로 진행된다 (시나리오 생성 후)

---

## 14. MVP에서 의도적으로 제외한 것 (v2 로드맵)

| 항목 | v2에서 추가 시기 | 이유 |
|---|---|---|
| PostgreSQL + PostGIS | 엔티티 수 1만 이상 시 | MVP는 SQLite + MF 기존 그래프로 충분 |
| Neo4j 듀얼 DB | 그래프 탐색 쿼리 필요 시 | MF 기존 Zep/DozerDB 활용 |
| Entity Resolution | 자동 식별 필요 시 | MVP는 정적 military_vessels.json으로 수동 매핑 |
| stix2 온톨로지 표준화 | 외부 시스템 연동 시 | MF 기존 LLM 온톨로지로 충분 |
| Action Layer | 시뮬레이션 결과로 자동 조치 시 | MVP는 읽기 전용 |
| 스냅샷 브랜칭 | 라이브 데이터와 시뮬레이션 분리 필요 시 | MVP는 별도 시뮬레이션 DB |
| 다중 피드 통합 | 항공/위성/지진 등 추가 시 | MVP는 AIS 선박만 |
| 지정학 시나리오 엔진 | OASIS 메타포의 한계 도달 시 | MVP는 소셜미디어 매핑으로 충분 |
| 스키마 버전관리 | 온톨로지 안정화 후 | 불필요한 복잡도 |
| Vue → Next.js 마이그레이션 | 프론트엔드 통합 깊이 필요 시 | MVP는 별도 실행 |

---

## 15. Risks & Mitigations

| 리스크 | 심각도 | 완화 방안 |
|---|---|---|
| ShadowBroker AIS 데이터에 군함이 부족할 수 있음 | Medium | Carrier Tracker(OSINT 기반 항모 추적) 병행 사용 + 테스트용 시드 문서 수동 작성 옵션 |
| MiroFish 온톨로지가 지정학 도메인에 부적합한 스키마 생성 | Medium | `simulation_requirement` 프롬프트 정교화 + 온톨로지 수동 보정 API |
| OASIS 시뮬레이션이 소셜미디어 메타포에서 비현실적 결과 생성 | Medium | 에이전트 persona 프롬프트에 행동 가이드 포함 + 결과 필터링 |
| LLM API 비용 초과 | Low | 시뮬레이션 라운드 수 제한 (기본 10), 캐싱 |
| ShadowBroker/MiroFish API 변경 | Low | 클라이언트 어댑터 패턴으로 격리 |

---

## 16. Conventions

### 코드 스타일
- Python: 프로젝트 내 린터 없음 (ShadowBroker/MiroFish 모두 린터 설정 없음)
- TypeScript: ShadowBroker의 eslint + tailwind 설정 따름
- 커밋 메시지: Conventional Commits (`feat:`, `fix:`, `docs:`)

### 패키지 관리
- Python: `uv` 사용 (`pip install` 금지 — MiroFish AGENTS.md 규칙 준수)
- Node.js: `npm`

### 네이밍
- 파일명: `snake_case.py`, `PascalCase.tsx`
- API 경로: `kebab-case` 아닌 `snake_case` (MiroFish 관례)
- 환경변수: `UPPER_SNAKE_CASE`
