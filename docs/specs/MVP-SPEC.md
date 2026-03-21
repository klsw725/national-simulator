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
├── docs/
│   └── specs/
│       └── MVP-SPEC.md          # 이 문서
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

- [x] ShadowBroker에서 실시간 선박 데이터를 수집하여 시드 문서를 자동 생성할 수 있다
- [x] 시드 문서로부터 MiroFish 파이프라인이 온톨로지 → 그래프 → 프로필 → 시뮬레이션을 완료한다
- [x] 시뮬레이션 결과가 GeoJSON으로 변환되어 지도 위에 표시된다
- [x] 최소 1개 시나리오(남중국해)를 처음부터 끝까지 실행할 수 있다
- [x] 전체 프로세스가 사용자 개입 없이 자동으로 진행된다 (시나리오 생성 후)

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

---

## 17. Design Decisions (아키텍처 결정 근거)

이 섹션은 "왜 이렇게 설계했는가"에 대한 기록이다. 8개의 탐색/검증 에이전트와 Oracle 아키텍처 리뷰를 통해 도출되었다.

### 17.1 팔란티어 온톨로지 vs Neo4j 지식 그래프

**결론: 팔란티어의 개념을 채택하되, 구현은 그래프 DB 위에 한다.**

팔란티어 Foundry의 온톨로지는 Neo4j 같은 지식 그래프가 **아니다**. 내부적으로 Apache Iceberg(컬럼형 테이블) 위에 구축된 타입드 객체 저장소이며, "그래프"는 FK 조인으로 쿼리 시점에 생성되는 논리적 투영이다.

#### 7대 구조적 차이점

| 차원 | 팔란티어 온톨로지 | MiroFish 현재 (Neo4j) |
|---|---|---|
| 저장 모델 | 컬럼형 테이블 (Iceberg/Parquet) | 네이티브 그래프 (노드+엣지 포인터 연결) |
| 관계(Link) 구현 | FK 조인 또는 조인 테이블. **관계에 속성 없음** | 네이티브 엣지에 fact/fact_type 속성 |
| 스키마 관리 | 필수, 버전관리, 브랜칭, 마이그레이션 | LLM 즉석 생성, 버전관리 없음 |
| Action (쓰기 연산) | 1등 시민 — 스키마 정의된 트랜잭셔널 쓰기 | 없음 |
| Entity Resolution | 비파괴적, 되돌리기 가능, 이력 보존 (Gotham) | 이름 기반 MERGE (파괴적) |
| 시공간 모델링 | 1등 시민 — Track/Observation API (Gotham) | 없음 |
| 출처(Provenance) | 모든 쓰기에 출처 메타데이터 내장 | 없음 |

#### 팔란티어 구조를 복제하면 안 되는 이유

OSINT 분석에는 그래프 DB가 팔란티어의 테이블형 구조보다 유리하다:

1. **다중 홉 그래프 탐색**: "용의자로부터 3홉 내 모든 연결"은 Neo4j에서 O(k), 팔란티어에서는 반복 조인 필요
2. **관계 속성**: OSINT에서 관계의 `confidence_score`, `source`, `timestamp`는 필수. 팔란티어는 관계에 속성 불가 (reification 필요)
3. **패턴 매칭**: Cypher의 `MATCH (a)-[:KNOWS*2..4]->(b) WHERE b.isSuspicious`는 인텔리전스 분석 핵심

#### 팔란티어에서 가져온 것 vs 안 가져온 것

| 채택 | 미채택 |
|---|---|
| 타입드 Object Types (엔티티 스키마) | 컬럼형 테이블 저장 |
| 타입드 Link Types (관계 스키마) | FK 조인 기반 관계 |
| Action Types (쓰기 연산 추상화) | 마이크로서비스 6개 아키텍처 |
| 비파괴적 Entity Resolution (Gotham) | Object Data Funnel (Iceberg 파이프라인) |
| 시공간 1등 시민 모델링 (Track/Observation) | — |
| 출처(Provenance) 추적 | — |
| 스키마 버전관리 | — |

---

### 17.2 OpenCTI 탈락 근거

**결론: OpenCTI는 과잉이다. `stix2` Python 라이브러리를 직접 사용한다.**

| 평가 항목 | OpenCTI | stix2 라이브러리 |
|---|---|---|
| 임베딩 가능성 | ❌ 독립 플랫폼 (5개 서비스, 18GB RAM) | ✅ pip install, 인프로세스 |
| 커스텀 SDO | ❌ TypeScript 소스 포크 필요 | ✅ `@CustomObject` 5줄 |
| pycti 독립 사용 | ❌ HTTP 클라이언트일 뿐 | N/A |
| 라이선스 | Apache 2.0 (CE) / Proprietary (EE) | BSD 3-Clause |

v2에서 `stix2`를 사용하여 커스텀 OSINT 엔티티를 정의하는 패턴:
```python
from stix2 import CustomObject, properties

@CustomObject('x-vessel', [
    ('mmsi', properties.StringProperty(required=True)),
    ('vessel_type', properties.StringProperty()),
    ('flag_state', properties.StringProperty()),
])
class Vessel(object):
    pass
```

---

### 17.3 OASIS 확장성 분석 결과

**결론: 확장 가능하지만 비공식적이다. MVP에서는 수정 없이 Twitter 메타포로 사용, v2에서 Platform 서브클래싱.**

탐색/검증 에이전트의 상반된 결과를 종합:

- `DefaultPlatformType`은 닫힌 enum (Twitter/Reddit만)
- **하지만** `OasisEnv.__init__()`은 `isinstance(platform, Platform)` 분기가 있어, 커스텀 Platform 인스턴스를 직접 전달하면 수용됨
- `getattr(self, action.value)` 디스패치 → Platform 서브클래스에 메서드만 추가하면 새 액션 동작
- `Channel`(비동기 큐)은 완전히 플랫폼 무관
- `PURCHASE_PRODUCT` 액션이 이미 소셜미디어 밖으로 확장된 선례

v2에서의 확장 방법 (OASIS 소스 ~20줄 수정):
1. `ActionType` enum에 새 값 추가 (typing.py)
2. `Platform` 서브클래스 생성 + 새 액션 핸들러 메서드
3. `database.py`의 `create_db()`에 새 테이블 추가
4. 커스텀 `UserInfo` 템플릿으로 에이전트 페르소나 변경

---

## 18. v2 Target Architecture (전체 5-레이어)

MVP 이후 진화할 최종 아키텍처. Oracle 아키텍처 리뷰 결과를 반영.

```
┌─────────────────────────────────────────────────────────────────────┐
│  Layer 5: FRONTEND (Next.js + MapLibre)                            │
│  ShadowBroker 지도 + 시뮬레이션 패널 + 보고서 + 온톨로지 브라우저     │
├─────────────────────────────────────────────────────────────────────┤
│  Layer 4: SIMULATION                                               │
│  ┌──────────────────────┐  ┌──────────────────────────────────┐    │
│  │ 지정학 시나리오 엔진    │  │ OASIS (정보 전파 서브 시뮬레이터)  │    │
│  │ (신규 구축)            │  │ (Platform 서브클래싱)             │    │
│  │ 상태 전이, 의사결정,    │  │ 여론 시뮬레이션, 소셜 반응        │    │
│  │ 행위자 목표/제약       │  │                                 │    │
│  └──────────┬───────────┘  └───────────────┬──────────────────┘    │
│             │ 시나리오 브랜치에서만 쓰기        │                       │
├─────────────┼──────────────────────────────┼───────────────────────┤
│  Layer 3: ACTION LAYER (PG append-only 이벤트)                     │
│  Action 정의 → 유효성 검증 → PG 기록 → 시나리오 상태 변경             │
│  승인 규칙 / RBAC / 감사 트레일 / 롤백                               │
├─────────────────────────────────────────────────────────────────────┤
│  Layer 2: ONTOLOGY (2-Tier)                                        │
│                                                                     │
│  PostgreSQL + PostGIS (유일한 쓰기 권한, Source of Truth)             │
│  ┌─────────────────────┐  ┌────────────────────────────────────┐   │
│  │ Tier 1: 원시 관측     │  │ Tier 2: STIX-aligned 해소 엔티티   │   │
│  │ flights, vessels,    │  │ x-vessel, x-aircraft, threat-actor │   │
│  │ tracks, incidents    │  │ relationship, identity, location   │   │
│  │ (PostGIS + 시계열)    │  │ (stix2 라이브러리로 검증)           │   │
│  └─────────────────────┘  └────────────────────────────────────┘   │
│  ┌──────────────────┐  ┌───────────────────┐  ┌────────────────┐   │
│  │ Entity Resolution │  │ Provenance        │  │ 시나리오 스냅샷  │   │
│  │ (경량 identity     │  │ (출처, 신뢰도)    │  │ (브랜치/동결)   │   │
│  │  graph + 수동 병합) │  │                   │  │                │   │
│  └──────────────────┘  └───────────────────┘  └────────────────┘   │
│                                                                     │
│  Neo4j (읽기 전용 투영, 비동기, 폐기/재구축 가능)                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ 엔티티 관계 그래프 → 다중 홉 탐색, 패턴 매칭, 중심성 분석       │   │
│  │ PG outbox → micro-batch 프로젝터 (1~10초 지연)                │   │
│  └──────────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────────┤
│  Layer 1: DATA SYNC (ShadowBroker → PG)                            │
│  20+ OSINT 피드 → Tier 1 원시 관측 upsert                           │
│             → Entity Resolution → Tier 2 STIX 엔티티                │
│             → PG outbox → Neo4j 투영                                │
└─────────────────────────────────────────────────────────────────────┘
```

### 2-Tier 온톨로지 설계 근거

STIX에 모든 것을 우겨넣으면 안 된다 (Oracle 리뷰 결과):

- **Tier 1 (원시 관측, Native PG)**: ADS-B/AIS 텔레메트리는 60초마다 갱신되는 고빈도 위치 데이터. STIX 객체로 만들면 과잉이고 성능 저하.
- **Tier 2 (STIX-aligned 해소 엔티티)**: Entity Resolution이 완료된 식별된 엔티티. 관계, 출처, 인시던트를 STIX 표준으로 관리.

### 시나리오/라이브 경계 (스냅샷 브랜칭)

시뮬레이션이 라이브 OSINT 데이터를 오염시키면 안 된다:

```
ShadowBroker 피드 → PG (라이브 세계) ← 읽기 전용
                         │
                    스냅샷 복제 (특정 시점)
                         ↓
               PG (시나리오 브랜치) ← 시뮬레이션 쓰기 전용
                    │
               시뮬레이션 결과만 시각화에 투영
```

### PG ↔ Neo4j 동기화 패턴

| 패턴 | 설명 |
|---|---|
| 쓰기 | 항상 PostgreSQL 먼저 → 성공 시 Neo4j에 투영 |
| 동기화 | PG 트랜잭셔널 outbox + micro-batch 프로젝터 (1~10초) |
| 충돌 | PostgreSQL이 진실의 원천 (Source of Truth) |
| 장애 | Neo4j 다운 시 → 서비스 지속 (그래프 쿼리만 불가) |
| 재구축 | Neo4j는 PG 데이터에서 언제든 재구축 가능 (disposable) |

### RDB + Graph DB 쿼리 분담

| 쿼리 유형 | 담당 DB | 이유 |
|---|---|---|
| 시공간 쿼리 (반경 50km 내 자산) | PG + PostGIS | 공간 인덱스 (R-tree) |
| 시계열 쿼리 (24시간 이동 경로) | PG (+ TimescaleDB 옵션) | 인덱스 스캔 O(log n) |
| 다중 홉 탐색 (3홉 내 연결) | Neo4j | 인접 리스트 O(k) |
| 패턴 매칭 (러시아 군함→NATO 항구) | Neo4j | Cypher 선언적 쿼리 |
| 중심성/커뮤니티 분석 | Neo4j GDS | 네이티브 그래프 알고리즘 |
| Entity Resolution 이력 | PG | ACID 트랜잭션 |
| Action 로그/감사 | PG | append-only, 불변 |
| 출처(Provenance) 추적 | PG | 구조화된 조회 |

---

## 19. Oracle Architecture Review (리스크 평가)

Oracle 에이전트가 전체 아키텍처를 리뷰한 결과. 6개 High 이상 리스크 식별.

| 심각도 | 리스크 | 상태 | 완화 방안 |
|---|---|---|---|
| **Critical** | OASIS 커플링 — 소셜미디어 시뮬레이터를 지정학 코어로 쓰면 안 됨 | MVP에서 해소 (Twitter 메타포) / v2에서 분리 | OASIS는 정보 전파 서브 시뮬레이터로만 사용. 지정학 코어는 v2에서 별도 구축 |
| **High** | Sync 엔진 설계 — row-by-row 동기화 실패 | v2에서 대응 | PG 트랜잭셔널 outbox + micro-batch 프로젝터 |
| **High** | 온톨로지 모델 불일치 — STIX는 ADS-B/AIS 텔레메트리용이 아님 | v2에서 대응 | 2-Tier 온톨로지: 원시 관측은 네이티브 PG, STIX는 해소 엔티티만 |
| **High** | 시나리오 경계 부재 — 시뮬레이션이 라이브 데이터 오염 가능 | MVP에서 해소 (별도 시뮬레이션 DB) | 스냅샷 브랜칭 패턴 |
| **High** | Action Layer 미명세 | v2에서 대응 | PG append-only 이벤트, 승인 규칙, RBAC, 감사, 롤백 |
| **High** | Entity Resolution 과잉 | MVP에서 해소 (수동 매핑) | v2: 경량 identity graph (불변 관측 + 신뢰도 링크 + 수동 병합/해제) |
| **Medium** | OpenCTI 과잉 | 해소 (stix2 직접 사용) | OpenCTI는 TAXII/ATT&CK 워크플로우 필요 시에만 재검토 |
| **Medium** | 프론트엔드 분리 (Vue + Next.js) | MVP에서 해소 (SB만 사용) | Next.js로 표준화, MF 워크플로우만 포팅 |
| **Medium** | 스키마 버전관리 과잉 | MVP에서 해소 (미포함) | DB 마이그레이션 + version 필드로 충분 |
| **Medium** | 성능 (~500 ops/sec) | 해소 | PG 충분, Neo4j 배치 인덱싱이면 가능 |

### Oracle 에스컬레이션 트리거

다음 조건 발생 시 아키텍처 재검토 필요:

- 대부분의 읽기 패턴이 지리공간/시계열이고 심층 그래프 탐색이 거의 없으면 → **Neo4j 제거, PG 단독으로 전환**
- TAXII 교환, ATT&CK 매핑, 분석관 협업, 외부 CTI 연동이 초기에 필요하면 → **OpenCTI 재검토**
- 시뮬레이터가 물류, 지휘 체계, 운동학적 효과를 모델링해야 하면 → **OASIS 완전 대체**

---

## 20. Entity Resolution 설계 (v2)

### Gotham 패턴: 비파괴적, 되돌리기 가능

팔란티어 Gotham의 Entity Resolution은 독립 이력 보존, 되돌리기 가능, 재귀적 해소 평탄화가 핵심:

```python
class ResolutionBag:
    canonical_id: str           # 대표 ID
    constituent_ids: list[str]  # 구성 엔티티 ID들
    winner_id: str              # 해소 후 속성 기록용
    created_by: str             # 해소 실행자
    created_at: datetime
    reversible: bool = True

    def resolve(self, other_id: str) -> None:
        """두 엔티티 병합 — 양쪽 이력 보존"""
        pass

    def unresolve(self, id: str) -> None:
        """병합 해제 — 해소 후 기록된 속성은 winner에 유지"""
        pass
```

### v1 (MVP) 단순화

MVP에서는 Entity Resolution 없이 정적 `military_vessels.json`으로 수동 매핑.

### v2 경량 Identity Graph

Palantir 전체 구현 대신 경량 버전:
- 불변 관측(observation) 보존
- 후보 매칭 테이블 + 신뢰도 점수
- 선택된 엔티티 클래스에 대해서만 수동 병합/해제 지원
- 출처(provenance) 추적

---

## 21. Performance Analysis

### 데이터 볼륨

ShadowBroker의 실시간 데이터 규모:
- ~5,000 항공기 (60초마다 갱신)
- ~25,000 선박 (실시간 WebSocket)
- ~2,000 위성 (60초마다 갱신)
- ~1,000 GDELT 이벤트 (6시간마다)
- 합계: **~33,000 엔티티 / 60초 = ~550 업데이트/초**

### 처리 능력

| 구성요소 | 처리량 | 충분 여부 |
|---|---|---|
| PostgreSQL 쓰기 | ~10,000+ TPS (배치) | ✅ 여유 |
| PostGIS 공간 쿼리 | ~1,000+ QPS (인덱싱된) | ✅ 여유 |
| Neo4j 관계 쓰기 | ~1,000-3,000 MERGE/초 (배치) | ✅ 배치면 충분 |
| PG→Neo4j 프로젝션 | micro-batch (1-10초 지연) | ✅ eventual consistency |

### 진짜 병목

- 동기식 Entity Resolution (LLM 호출 시)
- 프로젝션 갱신 빈도 (전체 재구축 vs 변경분만)
- 핫 인덱스 경합 (Neo4j MERGE on 자주 갱신되는 노드)

---

## 22. Investigation Summary (탐색 에이전트 결과 요약)

총 8개의 탐색/검증 에이전트 실행 결과 요약.

### Round 1: 초기 탐색 (4개 에이전트)

| 에이전트 | 목적 | 핵심 발견 |
|---|---|---|
| librarian #1 | 팔란티어 Foundry 기술 아키텍처 | 그래프 DB 아님, Iceberg 테이블 + 6개 마이크로서비스, Link에 속성 없음 |
| librarian #2 | Gotham vs Foundry 비교 | Gotham: 비파괴적 Entity Resolution, Track/Observation API, 연합 소스 |
| explore #1 | MiroFish 그래프/온톨로지 구현 | 전체 데이터 흐름 매핑 (텍스트→온톨로지→그래프→프로필→시뮬레이션), Zep/DozerDB 팩토리 패턴 |
| librarian #3 | 오픈소스 팔란티어 대안 | TypeDB 가장 유사, STIX 2.1이 Gotham 등가물, Action Layer는 오픈소스에 없음 |

### Round 2: 검증 (4개 에이전트)

| 에이전트 | 목적 | 핵심 발견 |
|---|---|---|
| explore #2 | OASIS 확장성 검증 (MiroFish 코드) | ActionType 닫힌 enum, OasisEnv 하드코딩, 프로필 포맷 하드코딩 |
| librarian #4 | OASIS 확장성 검증 (GitHub 소스) | Platform 서브클래싱 가능, Channel 재사용 가능, PURCHASE_PRODUCT 선례 |
| librarian #5 | OpenCTI 아키텍처 | 5서비스/18GB, 커스텀 SDO 불가, stix2로 대체 가능 |
| **oracle** | 전체 아키텍처 리뷰 | 6개 High 리스크, 2-Tier 온톨로지 필요, 시나리오 경계 부재, OASIS는 서브모듈로 제한 |

---

## 23. SPEC ↔ PRD 매핑

### 실행 순서 및 의존성

```
PRD 1 (gateway-api-foundation)
  │
  ├──→ PRD 2 (shadowbroker-integration)
  │       │
  │       └──→ PRD 3 (seed-generation)
  │               │
  │               └──→ PRD 4 (simulation-orchestration)
  │                       │
  │                       └──→ PRD 5 (result-projection)
  │                               │
  └───────────────────────────────┴──→ PRD 6 (frontend-simulation-ui)
```

### SPEC 섹션 → PRD 매핑 (정방향)

| SPEC 섹션 | 담당 PRD | 비고 |
|---|---|---|
| **§1** Executive Summary | 전체 | 프로젝트 목표, 소스 프로젝트 정의 |
| **§2** Architecture | PRD 1 | 4-레이어 구조, 설계 원칙 |
| **§3.1.1** Seed Generator | **PRD 3** | `SeedGenerator`, `VesselMapper` 클래스 |
| **§3.1.2** ShadowBroker Client | **PRD 2** | `ShadowBrokerClient` 클래스. ⚠️ SPEC의 API 엔드포인트는 실제와 다름 — PRD 2가 실제 검증 |
| **§3.1.3** MiroFish Pipeline Adapter | **PRD 4** | `MiroFishClient`, `SimulationOrchestrator` 클래스. ⚠️ SPEC의 API 엔드포인트는 실제와 다름 — PRD 4가 실제 검증 |
| **§3.1.4** Result Projector | **PRD 5** | `ResultProjector` 클래스, GeoJSON 변환 |
| **§3.2** 기존 코드 활용 (9개 모듈) | PRD 2, 4 | SB/MF 모듈을 HTTP API로 호출 |
| **§4 Phase 1** 시나리오 생성 | **PRD 3** | OSINT 데이터 → 시드 문서 변환 흐름 |
| **§4 Phase 2** MiroFish 파이프라인 | **PRD 4** | 온톨로지 → 그래프 → 프로필 → 시뮬레이션 6단계 |
| **§4 Phase 3** 결과 시각화 | **PRD 5, 6** | GeoJSON 변환(PRD 5) + 지도 렌더링(PRD 6) |
| **§5.1** ScenarioConfig | PRD 1 | SQLite scenarios 테이블 |
| **§5.2** SeedDocument | PRD 1, 3 | SQLite seeds 테이블(PRD 1), 생성 로직(PRD 3) |
| **§5.3** SimulationResult | PRD 1, 4 | SQLite simulation_results 테이블(PRD 1), 파이프라인(PRD 4) |
| **§5.4** Military Vessel Mapping | **PRD 3** | `military_vessels.json` + `VesselMapper` |
| **§5.5** Actor GeoJSON | **PRD 5** | `ResultProjector` 출력 형식 |
| **§6** API Design (12 endpoints) | PRD 1, 2, 3, 4, 5 | 시나리오 CRUD(PRD 1), OSINT 프록시(PRD 2), 시드(PRD 3), 시뮬레이션(PRD 4), 결과(PRD 5) |
| **§7** Tech Stack | PRD 1, 6 | 백엔드(PRD 1), 프론트엔드(PRD 6) |
| **§8** Project Structure | PRD 1, 6 | 백엔드 구조(PRD 1), 프론트엔드 구조(PRD 6) |
| **§9** Environment Variables | PRD 1 | `.env.example` |
| **§10** Dependencies | PRD 1, 6 | pyproject.toml(PRD 1), package.json(PRD 6) |
| **§11** Prompt Customization | **PRD 3, 4** | 시드 생성 프롬프트(PRD 3), simulation_requirement + action_mapping(PRD 4) |
| **§12** Timeline | 전체 | 아래 주차별 매핑 참조 |
| **§13** Success Criteria | 전체 | 각 PRD의 E2E 마일스톤에서 검증 |
| **§14** v2 Roadmap | 해당 없음 | MVP PRD 범위 밖 |
| **§15** Risks & Mitigations | 전체 | 각 PRD에 위험 섹션 포함 |
| **§16** Conventions | PRD 1 | 코드 스타일, 패키지 관리, 네이밍 |
| **§17** Design Decisions | 해당 없음 | 참고 자료 (PRD 실행에 직접 영향 없음) |
| **§18** v2 Target Architecture | 해당 없음 | v2 범위 |
| **§19** Oracle Review | 해당 없음 | 참고 자료 |
| **§20** Entity Resolution | 해당 없음 | v2 범위 |
| **§21** Performance Analysis | 해당 없음 | 참고 자료 |
| **§22** Investigation Summary | 해당 없음 | 참고 자료 |

### PRD → SPEC 매핑 (역방향)

| PRD | SPEC 섹션 | 핵심 산출물 |
|---|---|---|
| **PRD 1** gateway-api-foundation | §2, §5.1-5.3, §6, §7, §8, §9, §10, §16 | FastAPI 앱, SQLite 스키마, Docker Compose, 환경 설정 |
| **PRD 2** shadowbroker-integration | §3.1.2, §3.2 | ShadowBroker HTTP 클라이언트, OSINT 프록시 엔드포인트 |
| **PRD 3** seed-generation | §3.1.1, §4 Phase 1, §5.4, §11 | 군함 DB, Vessel Mapper, GDELT 추출기, LLM 시드 생성기 |
| **PRD 4** simulation-orchestration | §3.1.3, §4 Phase 2, §11 | MiroFish HTTP 클라이언트, 6단계 파이프라인 오케스트레이터 |
| **PRD 5** result-projection | §3.1.4, §4 Phase 3, §5.5 | 행위자 좌표 DB, 결과 분석기, GeoJSON 변환기 |
| **PRD 6** frontend-simulation-ui | §2, §4 Phase 3, §7 프론트엔드, §13 | 시뮬레이션 UI, MapLibre 오버레이, 타임라인, 보고서 뷰어 |

### 타임라인 → PRD 매핑

| 주차 | SPEC §12 마일스톤 | PRD | PRD 마일스톤 |
|---|---|---|---|
| **W1** | 프로젝트 셋업 + SB 클라이언트 | PRD 1 (M1~M5) + PRD 2 (M1~M2) | FastAPI 앱 + Docker Compose + SB 클라이언트 |
| **W2** | 군함 매핑 + 시드 생성기 | PRD 2 (M3~M5) + PRD 3 (M1~M4) | SB 연동 완성 + 군함 DB + 시드 생성기 |
| **W3** | MiroFish 어댑터 + 파이프라인 | PRD 3 (M5~M6) + PRD 4 (M1~M4) | 시드 API + MF 클라이언트 + 파이프라인 |
| **W4** | 결과 프로젝터 + API 통합 | PRD 4 (M5~M6) + PRD 5 (M1~M5) | 파이프라인 E2E + GeoJSON 변환 + API |
| **W5-6** | 프론트엔드 시각화 | PRD 6 (M1~M7) | Next.js 앱 + 지도 레이어 + 시나리오 UI + 타임라인 |
| **W7** | 통합 테스트 + 데모 준비 | PRD 6 (M8) | 남중국해 시나리오 E2E 데모 |

### API 엔드포인트 오류 정정 (PRD 검증 결과)

> **중요**: 본 SPEC §3.2, §4, §6에 기술된 ShadowBroker/MiroFish API 엔드포인트는 초기 설계 시점의 추정치이며, 실제 소스 코드와 다른 부분이 있다. **실제 구현 시에는 아래 PRD의 검증된 엔드포인트를 따른다.**

| 항목 | SPEC 기술 (추정) | PRD 검증 결과 (실제) | 참조 PRD |
|---|---|---|---|
| SB 선박 데이터 | `GET /api/ships` | `GET /api/live-data/fast` → `ships` 필드 | PRD 2 §3.1 |
| SB 분쟁 이벤트 | `GET /api/geopolitics` | `GET /api/live-data/slow` → `gdelt` 필드 | PRD 2 §3.1 |
| MF 온톨로지 생성 | `POST /api/ontology/generate` | `POST /api/graph/ontology/generate` (multipart) | PRD 4 §3.1 |
| MF 프로필 생성 | `POST /api/profiles/generate` | `POST /api/simulation/prepare` (내부 포함) | PRD 4 §3.1 |
| MF 시뮬레이션 실행 | `POST /api/simulation/run` | `POST /api/simulation/start` | PRD 4 §3.1 |
| MF 시뮬레이션 상태 | `GET /api/simulation/{id}/status` | `GET /api/simulation/{id}/run-status` | PRD 4 §3.3 |

---

## 24. v2 구현 현황 (2026-03-21)

### 완료된 v2 PRD

| PRD | 마일스톤 | 상태 |
|-----|---------|------|
| v2-postgresql-postgis | M1-M4 | ✅ 전체 완료 (PostGIS + observations + GIST 인덱스) |
| v2-stix2-ontology | M1-M4 | ✅ 전체 완료 (커스텀 SDO + Tier 2) |
| v2-snapshot-branching | M1-M4 | ✅ 전체 완료 (OSINT 스냅샷 격리) |
| v2-action-layer | M1-M4 | ✅ 전체 완료 (RBAC + 승인 + 보상 롤백) |
| v2-realtime-monitoring | M1-M4 | ✅ 전체 완료 (실시간 시뮬레이션 모니터링) |
| v2-pipeline-checkpoints | M1-M3 | ✅ 전체 완료 (Human-in-the-Loop 체크포인트) |
| multi-feed-integration | M1-M4 | ✅ 전체 완료 (다중 OSINT 피드) |
| v2-entity-resolution | M1-M4 | ✅ 전체 완료 (매칭 엔진 + 자동 해소 + 검토 API) |
| v2-schema-versioning | M1-M4 | ✅ 전체 완료 (온톨로지 버전관리 + diff + 파이프라인 연동) |

### 부분 완료 v2 PRD (OASIS 런타임 의존)

| PRD | 완료 | 잔여 | 블로커 |
|-----|------|------|--------|
| v2-oasis-platform-subclassing | M1-M3 | M4 (통합 테스트) | OASIS 설치 환경 필요 |
| v2-geopolitics-scenario-engine | M1-M3 | M4 (OASIS 양방향 연동) | OASIS 설치 환경 필요 |

### PRD 외 추가 구현

| 기능 | 파일 | 설명 |
|------|------|------|
| 지정학 엔진 API | `geopolitics/router.py` | POST /api/geopolitics/simulate, POST /api/geopolitics/event |
| OSINT 관측 수집 파이프라인 | `services/observation_collector.py` | SB → observations INSERT + Entity Resolution 자동 실행 |

### v2 아키텍처 현재 상태

```
Gateway API (FastAPI, port 4000)
├── /api/scenario/*          시나리오 CRUD + 시드/시뮬레이션
├── /api/osint/*             SB 프록시 + OSINT 수집 파이프라인
├── /api/actions             RBAC + 승인 + 보상 롤백
├── /api/ontology/versions   온톨로지 버전관리 + diff
├── /api/resolution          Entity Resolution 매칭 + 검토
├── /api/geopolitics         지정학 시뮬레이션 엔진
│
├── PostgreSQL + PostGIS
│   ├── scenarios, seeds, simulation_results
│   ├── stix_objects (Tier 2)
│   ├── observations (Tier 1, PostGIS geom)
│   ├── ontology_versions
│   ├── resolution_candidates, resolution_decisions
│   ├── action_log (RBAC + 감사)
│   ├── scenario_snapshots
│   └── geopolitics_events
│
├── Entity Resolution
│   ├── Matcher (정확 MMSI/ICAO24 + 퍼지 이름)
│   └── Resolver (자동 해소 threshold 0.85 + 수동 검토)
│
├── Geopolitics Engine
│   ├── ActorState (위협/압력/자원 + 목표/제약)
│   ├── DecisionEngine (규칙 기반 의사결정)
│   └── CascadeEvents (연쇄 반응 + 감쇠)
│
└── OASIS Integration
    ├── GeopoliticsPlatform (12 액션 타입)
    └── GeopoliticsActionType (external/mirofish-backend)
```
