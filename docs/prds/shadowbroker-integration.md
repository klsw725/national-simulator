# PRD: ShadowBroker Integration

> Status: Draft
> Created: 2026-03-20
> Dependencies: PRD 1 (gateway-api-foundation)
> 관련 스펙: `specs/MVP-SPEC.md` Section 3.1.2, 3.2

---

## 1. 문제 정의

OSINT Simulator는 ShadowBroker의 실시간 OSINT 데이터(선박, 항공기, GDELT 분쟁 이벤트 등)를 소비해야 한다. MVP-SPEC.md에 기술된 ShadowBroker API 엔드포인트(`/api/ships`, `/api/geopolitics`)는 **실제로 존재하지 않는다**. 실제 ShadowBroker API는 데이터를 티어별로 제공하며(`/api/live-data/fast`, `/api/live-data/slow`), 좌표 필드명도 데이터 소스에 따라 다르다(`lng` vs `lon`).

## 2. 솔루션 개요

- **ShadowBroker HTTP 클라이언트** — httpx 비동기 클라이언트로 실제 SB API 호출
- **OSINT 프록시 엔드포인트** — 게이트웨이에서 SB 데이터를 포워딩하는 프록시 레이어
- **데이터 정규화** — 좌표 필드명 차이(lng/lon)를 인지하되 통일하지 않음 (SB 내부 뷰포트 필터링 보호)

## 3. 기술 상세

### 3.1 ShadowBroker 실제 API 엔드포인트 (검증 완료)

> **경고**: MVP-SPEC.md의 `/api/ships`, `/api/geopolitics` 등은 존재하지 않음

| 실제 엔드포인트 | 메서드 | 용도 | 주요 파라미터 |
|---|---|---|---|
| `/api/live-data/fast` | GET | 선박, 항공기, 위성, CCTV 등 (15초 갱신) | `s`, `w`, `n`, `e` (bbox, optional) |
| `/api/live-data/slow` | GET | GDELT, 뉴스, 지진, 날씨 등 (120초 갱신) | `s`, `w`, `n`, `e` (bbox, optional) |
| `/api/live-data` | GET | 전체 데이터 (fast + slow) | 없음 |
| `/api/viewport` | POST | AIS 스트림 뷰포트 설정 | `{s, w, n, e}` |
| `/api/health` | GET | SB 상태 확인 | 없음 |
| `/api/refresh` | GET | 데이터 강제 갱신 | 없음 |

### 3.2 데이터 소스별 좌표 필드명 (절대 통일 금지)

| 데이터 소스 | 위도 | 경도 | 비고 |
|---|---|---|---|
| ships (AIS) | `lat` | **`lng`** | 군함 포함 |
| flights (전종류) | `lat` | **`lng`** | commercial, military, private |
| satellites | `lat` | **`lng`** | |
| CCTV | `lat` | **`lon`** | TFL, LTA, Austin, NYC |
| KiwiSDR | `lat` | **`lon`** | |
| 나머지 (지진, 화재 등) | `lat` | **`lng`** | |

### 3.3 `/api/live-data/fast` 응답 구조 (선박 관련)

```json
{
  "ships": [
    {
      "mmsi": 123456789,
      "name": "USS GERALD FORD",
      "lat": 15.2,
      "lng": 115.8,
      "speed": 12.5,
      "course": 180,
      "heading": 175,
      "shiptype": 35,
      "flag": "US",
      "destination": "WESTERN PACIFIC",
      "imo": 1234567
    }
  ],
  "commercial_flights": [...],
  "military_flights": [...],
  "freshness": {
    "ships": "2026-03-20T14:30:00Z",
    "flights": "2026-03-20T14:30:05Z"
  }
}
```

### 3.4 `/api/live-data/slow` 응답 구조 (GDELT 관련)

```json
{
  "gdelt": {
    "type": "FeatureCollection",
    "features": [
      {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [115.8, 15.2]},
        "properties": {
          "goldstein_scale": -5.2,
          "event_code": "190",
          "actor1": "USA",
          "actor2": "CHN",
          "source_url": "..."
        }
      }
    ]
  },
  "news": [...],
  "freshness": {
    "gdelt": "2026-03-20T14:25:00Z"
  }
}
```

### 3.5 ShadowBroker HTTP 클라이언트

```python
# backend/app/clients/shadowbroker.py
class ShadowBrokerClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = httpx.AsyncClient(base_url=base_url, timeout=30.0)

    async def get_fast_data(self, bbox: BBox | None = None) -> dict:
        """GET /api/live-data/fast — 선박, 항공기, 위성 등"""

    async def get_slow_data(self, bbox: BBox | None = None) -> dict:
        """GET /api/live-data/slow — GDELT, 뉴스, 지진 등"""

    async def get_ships(self, bbox: BBox | None = None) -> list[dict]:
        """fast 데이터에서 ships 필드만 추출"""

    async def get_gdelt(self, bbox: BBox | None = None) -> dict:
        """slow 데이터에서 gdelt 필드만 추출 (GeoJSON)"""

    async def set_viewport(self, bbox: BBox) -> None:
        """POST /api/viewport — AIS 스트림 뷰포트 설정"""

    async def health_check(self) -> dict:
        """GET /api/health — SB 상태 확인"""
```

### 3.6 OSINT 프록시 라우터

```python
# backend/app/routers/osint.py
router = APIRouter(prefix="/api/osint")

@router.get("/live_data/fast")
async def proxy_fast_data(s: float = None, w: float = None, n: float = None, e: float = None):
    """SB /api/live-data/fast 프록시"""

@router.get("/live_data/slow")
async def proxy_slow_data(s: float = None, w: float = None, n: float = None, e: float = None):
    """SB /api/live-data/slow 프록시"""

@router.get("/live_data")
async def proxy_all_data():
    """SB /api/live-data 프록시"""
```

## 4. 마일스톤

- [ ] **M1: ShadowBroker HTTP 클라이언트 구현** — httpx 비동기 클라이언트. `get_fast_data()`, `get_slow_data()`, `get_ships()`, `get_gdelt()`, `set_viewport()`, `health_check()` 메서드 구현. bbox 파라미터 지원.
  - 검증: SB 실행 상태에서 `get_ships()` 호출 → 선박 데이터 수신

- [ ] **M2: OSINT 프록시 엔드포인트 구현** — `/api/osint/live_data/fast`, `/api/osint/live_data/slow`, `/api/osint/live_data` 라우트 등록. bbox 쿼리 파라미터 포워딩.
  - 검증: `curl localhost:4000/api/osint/live_data/fast` → SB 데이터 반환

- [ ] **M3: ETag 캐싱 지원** — SB가 반환하는 ETag 헤더를 게이트웨이에서도 전달. If-None-Match 헤더 포워딩으로 불필요한 데이터 전송 방지.
  - 검증: 동일 요청 연속 2회 → 2번째 요청 304 응답

- [ ] **M4: 에러 핸들링 + 연결 상태 관리** — SB 미기동 시 적절한 에러 응답 (503). 타임아웃 설정. 연결 재시도 로직.
  - 검증: SB 미기동 상태에서 `/api/osint/live_data/fast` → 503 + 명확한 에러 메시지

- [ ] **M5: 연동 검증** — SB를 실행한 상태에서 게이트웨이 OSINT 프록시로 데이터 조회. 선박 데이터의 `lng` 필드, GDELT GeoJSON의 `coordinates` 필드 확인.
  - 검증: 게이트웨이 → SB 전체 데이터 흐름 정상 동작

## 5. 성공 기준

- 게이트웨이 OSINT 프록시로 ShadowBroker의 모든 실시간 데이터에 접근 가능
- bbox 파라미터로 관심 해역의 데이터만 필터링 가능
- ShadowBroker 미기동 시 명확한 에러 응답 반환
- 좌표 필드명이 SB 원본 그대로 전달됨 (lng/lon 차이 유지)

## 6. 위험 및 완화

| 위험 | 완화 |
|------|------|
| SB AIS 데이터에 군함이 부족 | Carrier Tracker 데이터도 ships에 포함됨 확인. 부족 시 테스트용 시드 문서 수동 작성 옵션 제공 (PRD 3) |
| SB API 응답 구조 변경 | 클라이언트 어댑터 패턴으로 격리. 응답 파싱 로직을 클라이언트 내부에 캡슐화 |
| 네트워크 지연 / 타임아웃 | httpx 타임아웃 30초 설정. 재시도 1회. 캐싱으로 반복 요청 최소화 |

## 7. 참고

### 관련 PRD
- **PRD 1 (gateway-api-foundation)** — 게이트웨이 앱 기반
- **PRD 3 (seed-generation)** — SB 클라이언트를 사용하여 선박/GDELT 데이터 소비

### 소스 프로젝트 참조
- ShadowBroker 백엔드: `/home/swlee/Shadowbroker/backend/main.py` (라우트 정의)
- 데이터 구조: `/home/swlee/Shadowbroker/backend/services/fetchers/_store.py`
- AIS 스트림: `/home/swlee/Shadowbroker/backend/services/ais_stream.py`

## 진행 로그

| 날짜 | 상태 | 내용 |
|------|------|------|
| 2026-03-20 | Draft | PRD 초안 작성 |
