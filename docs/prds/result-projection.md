# PRD: Result Projection

> Status: Draft
> Created: 2026-03-20
> Dependencies: PRD 1 (gateway-api-foundation), PRD 4 (simulation-orchestration)
> 관련 스펙: `specs/MVP-SPEC.md` Section 3.1.4, 4 Phase 3, 5.5

---

## 1. 문제 정의

MiroFish 시뮬레이션은 소셜미디어 메타포(트위터 포스트, 리포스트, 인용)로 결과를 생성한다. 이 결과를 지도 시각화에 적합한 GeoJSON으로 변환해야 한다. 국가 행위자를 지리적 좌표에 매핑하고, 시뮬레이션 행동을 긴장 수준/입장/관계선으로 투영해야 한다.

핵심 과제:
- 시뮬레이션 에이전트 이름(예: "United States") → 지리 좌표 매핑
- 포스트 감정 분석 → 긴장 수준(0.0~1.0) 계산
- 에이전트 간 상호작용 → 동맹/적대 관계 라인
- GeoJSON FeatureCollection 생성 (Point + LineString)

## 2. 솔루션 개요

- **Actor Location Map** — 국가/기관별 대표 좌표 데이터 (수도 좌표 + 군함 위치 오버라이드)
- **Result Projector** — 시뮬레이션 결과 분석 + GeoJSON 변환
- **Relationship Analyzer** — 에이전트 간 상호작용 패턴에서 관계 유형 추출
- **GeoJSON/Report API** — GET `/api/scenario/{id}/geojson`, GET `/api/scenario/{id}/report`

## 3. 기술 상세

### 3.1 국가 행위자 좌표 매핑

```json
// backend/app/data/actor_locations.json
{
  "United States": {"lat": 38.9072, "lng": -77.0369, "capital": "Washington D.C."},
  "China": {"lat": 39.9042, "lng": 116.4074, "capital": "Beijing"},
  "Japan": {"lat": 35.6762, "lng": 139.6503, "capital": "Tokyo"},
  "South Korea": {"lat": 37.5665, "lng": 126.9780, "capital": "Seoul"},
  "Philippines": {"lat": 14.5995, "lng": 120.9842, "capital": "Manila"},
  "Taiwan": {"lat": 25.0330, "lng": 121.5654, "capital": "Taipei"},
  "Russia": {"lat": 55.7558, "lng": 37.6173, "capital": "Moscow"},
  "North Korea": {"lat": 39.0392, "lng": 125.7625, "capital": "Pyongyang"},
  "Australia": {"lat": -35.2809, "lng": 149.1300, "capital": "Canberra"},
  "India": {"lat": 28.6139, "lng": 77.2090, "capital": "New Delhi"},
  "NATO": {"lat": 50.8503, "lng": 4.3517, "capital": "Brussels"},
  "ASEAN": {"lat": -6.2088, "lng": 106.8456, "capital": "Jakarta"},
  "United Nations": {"lat": 40.7489, "lng": -73.9680, "capital": "New York"}
}
```

좌표 결정 우선순위:
1. 시나리오 내 군함 위치 (가장 정확)
2. actor_locations.json 수도 좌표 (기본값)

### 3.2 Result Projector

```python
# backend/app/services/result_projector.py
class ResultProjector:
    def __init__(self, actor_locations: dict):
        self.locations = actor_locations

    def project_to_geojson(
        self,
        simulation_results: dict,
        vessel_locations: dict | None = None
    ) -> dict:
        """
        시뮬레이션 결과 → GeoJSON FeatureCollection.
        
        1. 에이전트별 포스트 집계 (발언 수, 감정 평균)
        2. 긴장 수준 계산 (감정 기반, 0.0~1.0)
        3. 입장 분류 (supportive/opposing/neutral/cautious)
        4. 핵심 발언 추출 (가장 영향력 있는 포스트)
        5. 관계 라인 생성 (REPOST/QUOTE 패턴 기반)
        """

    def _calculate_tension_level(self, posts: list[dict]) -> float:
        """포스트 감정 분석 기반 긴장 수준 계산"""

    def _classify_stance(self, posts: list[dict], actor: str) -> str:
        """에이전트 포스트 패턴으로 입장 분류"""

    def _extract_key_statement(self, posts: list[dict]) -> str:
        """가장 영향력 있는 발언 추출"""

    def _build_relationship_lines(self, all_posts: list[dict]) -> list[dict]:
        """에이전트 간 상호작용에서 관계 라인 GeoJSON 생성"""
```

### 3.3 GeoJSON 출력 구조

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {"type": "Point", "coordinates": [-77.0369, 38.9072]},
      "properties": {
        "feature_type": "actor",
        "actor": "United States",
        "actor_type": "superpower",
        "tension_level": 0.8,
        "stance": "opposing",
        "key_statement": "항행의 자유 작전을 지속할 것임을 재확인한다",
        "post_count": 5,
        "sentiment_avg": -0.3,
        "color": "#3b82f6"
      }
    },
    {
      "type": "Feature",
      "geometry": {
        "type": "LineString",
        "coordinates": [[-77.0369, 38.9072], [139.6503, 35.6762]]
      },
      "properties": {
        "feature_type": "relationship",
        "from_actor": "United States",
        "to_actor": "Japan",
        "relationship_type": "alliance",
        "strength": 0.9,
        "color": "#22c55e"
      }
    }
  ]
}
```

### 3.4 입장 분류 로직

| 입장 | 기준 | 색상 |
|------|------|------|
| `supportive` | 특정 진영 REPOST/LIKE 비율 높음 | `#22c55e` (green) |
| `opposing` | 반대 진영 QUOTE(부정적) 비율 높음 | `#ef4444` (red) |
| `neutral` | DO_NOTHING 비율 높음, 균형 잡힌 상호작용 | `#6b7280` (gray) |
| `cautious_ally` | 동맹 지지하되 직접 행동은 자제 | `#f59e0b` (amber) |

### 3.5 관계 라인 추출 로직

```python
# REPOST → 동맹 관계 (alliance)
# QUOTE_POST (긍정적 감정) → 지지 (support)
# QUOTE_POST (부정적 감정) → 적대 (hostile)
# FOLLOW → 외교적 관계 형성 (diplomatic)
# 상호 DO_NOTHING → 관계 없음 (no line)
```

## 4. 마일스톤

- [x] **M1: 국가 행위자 좌표 데이터 구축** — `actor_locations.json` 생성. 주요 국가 20개 + 국제기구(NATO, ASEAN, UN 등) 좌표. 시나리오 내 군함 위치 오버라이드 로직.
  - 검증: JSON 파일이 유효하고 주요 국가 좌표가 정확

- [x] **M2: 시뮬레이션 결과 분석 로직 구현** — 에이전트별 포스트 집계. 감정 기반 긴장 수준 계산. 입장 분류. 핵심 발언 추출.
  - 검증: 테스트 시뮬레이션 데이터 → 에이전트별 분석 결과 정확

- [x] **M3: GeoJSON 변환 구현** — Point 피처 (행위자 위치 + 속성). LineString 피처 (관계 라인). 색상 매핑. GeoJSON spec 준수.
  - 검증: 생성된 GeoJSON이 유효한 FeatureCollection이고 MapLibre에서 렌더링 가능

- [x] **M4: 관계 라인 추출 구현** — REPOST/QUOTE/LIKE 패턴에서 동맹/적대/외교 관계 추출. 관계 강도 계산. LineString GeoJSON 생성.
  - 검증: 시뮬레이션 데이터에서 의미 있는 관계 라인 추출

- [x] **M5: GeoJSON + Report API 통합** — GET `/api/scenario/{id}/geojson` → GeoJSON FeatureCollection 반환. GET `/api/scenario/{id}/report` → MiroFish 보고서 반환. DB 캐싱.
  - 검증: 완료된 시뮬레이션에 대해 GeoJSON/보고서 API 정상 응답

## 5. 성공 기준

- 시뮬레이션 결과가 유효한 GeoJSON FeatureCollection으로 변환된다
- 각 행위자의 위치, 긴장 수준, 입장, 핵심 발언이 포함된다
- 행위자 간 동맹/적대 관계가 LineString으로 표현된다
- GeoJSON이 MapLibre GL에서 정상 렌더링된다
- API를 통해 GeoJSON과 보고서를 조회할 수 있다

## 6. 위험 및 완화

| 위험 | 완화 |
|------|------|
| 시뮬레이션 에이전트 이름이 actor_locations.json에 없음 | Fuzzy matching 시도. 매칭 실패 시 시나리오 지역 중심점 사용. 로그 경고 |
| 감정 분석 기반 긴장 수준이 부정확 | 포스트 내용 + 액션 유형 + 대상 종합 판단. LLM 기반 감정 분석은 v2에서 추가 |
| 관계 라인이 너무 많아 시각적으로 복잡 | 강도 임계값 이하 관계 필터링. 프론트엔드에서 관계 토글 제공 (PRD 6) |

## 7. 참고

### 관련 PRD
- **PRD 4 (simulation-orchestration)** — 시뮬레이션 결과 제공
- **PRD 6a (frontend-foundation)** — 프론트엔드 프로젝트 기반 + MapLibre 지도
- **PRD 6c (simulation-visualization)** — GeoJSON을 지도에 렌더링

### 데이터 흐름
```
MiroFish 시뮬레이션 결과 (posts, actions)
  → Result Projector
    → GeoJSON FeatureCollection
      → 프론트엔드 MapLibre 레이어
```

## 진행 로그

| 날짜 | 상태 | 내용 |
|------|------|------|
| 2026-03-20 | Draft | PRD 초안 작성 |
