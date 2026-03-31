# PRD: 다중 피드 통합 (Multi-Feed Integration)

> Status: Complete
> Created: 2026-03-20
> Dependencies: PRD 6a (frontend-foundation)
> 관련 스펙: `specs/MVP-SPEC.md` Section 14 (v2 로드맵), Section 21 (Performance Analysis)
> 버전: v2.0

---

## 1. 문제 정의

MVP는 AIS 선박 데이터만 지도에 표시한다. 그러나 ShadowBroker는 이미 항공기(~5,000), 위성(~2,000), GDELT 분쟁 이벤트(~1,000)를 `/api/live-data/fast`와 `/api/live-data/slow`로 제공하고 있다. 이 데이터를 지도에 추가하면 OSINT 시각화 범위가 즉시 확장되고, 시뮬레이션 시드 생성 시 더 풍부한 컨텍스트를 제공할 수 있다.

핵심 과제:
- 항공기(상업/군용) GeoJSON 빌더 + MapLibre 레이어 추가
- 위성 GeoJSON 빌더 + MapLibre 레이어 추가
- GDELT 분쟁 이벤트 GeoJSON 빌더 + MapLibre 레이어 추가
- 레이어 토글 UI (선박/항공기/위성/GDELT 개별 on/off)
- 기존 데이터 폴링(useDataPolling)이 이미 fast/slow 데이터를 가져오므로 백엔드 변경 불필요

## 2. 솔루션 개요

- **GeoJSON 빌더 확장** — geoJSONBuilders.ts에 flights, satellites, gdelt 빌더 추가
- **MapLibre 레이어 추가** — 각 데이터 소스별 Source + Layer 등록
- **레이어 토글 UI** — 좌측 하단 레이어 패널 (체크박스 토글)
- **타입 정의 확장** — dashboard.ts에 Flight, Satellite, GdeltEvent 인터페이스 추가
- **백엔드 변경 없음** — 기존 OSINT 프록시가 이미 전체 데이터를 전달

## 3. 기술 상세

### 3.1 ShadowBroker 데이터 구조 (이미 제공 중)

**GET /api/live-data/fast 응답:**
```json
{
  "ships": [...],
  "commercial_flights": [...],
  "military_flights": [...],
  "satellites": [...],
  "freshness": {...}
}
```

**GET /api/live-data/slow 응답:**
```json
{
  "gdelt": [...],
  "freshness": {...}
}
```

### 3.2 항공기 데이터 구조

```typescript
interface Flight {
  icao24: string;
  callsign: string;
  lat: number;
  lng: number;
  alt: number;              // 고도 (feet)
  heading: number;
  speed_knots: number;
  model: string;             // 항공기 모델
  aircraft_category: string; // 분류
  country: string;
  military_type?: string;    // 군용기 유형 (fighter, bomber, transport 등)
}
```

**시각화:**
- 상업 항공기: 회색 아이콘, heading 방향 회전
- 군용 항공기: 노란색 아이콘 (선박과 동일 색상 체계)
- 지상(alt ≤ 100): 어두운 색상
- 클러스터링: zoom < 6

### 3.3 위성 데이터 구조

```typescript
interface Satellite {
  norad_id: number;
  name: string;
  lat: number;
  lng: number;
  alt_km: number;            // 궤도 고도 (km)
  velocity_km_s: number;     // 속도 (km/s)
  country: string;
  type: string;              // 위성 유형
}
```

**시각화:**
- 작은 원형 마커 (circle 레이어)
- 색상: 청록색 (#06b6d4)
- 크기: 작게 (radius 3)
- 클러스터링: zoom < 4

### 3.4 GDELT 분쟁 이벤트 구조

```typescript
// 이미 GeoJSON Feature로 제공됨
interface GdeltFeature {
  type: "Feature";
  geometry: { type: "Point"; coordinates: [number, number] };
  properties: {
    name: string;
    count: number;
    _headlines_list: string[];
    html: string;
  };
}
```

**시각화:**
- 히트맵 또는 펄스 원형 마커
- 색상: 주황색~빨간색 (이벤트 밀도에 따라)
- 크기: count 기반 보간
- 클릭 시 헤드라인 팝업

### 3.5 레이어 토글 UI

```typescript
interface ActiveLayers {
  ships: boolean;          // 기본 on
  flights_commercial: boolean;  // 기본 on
  flights_military: boolean;    // 기본 on
  satellites: boolean;     // 기본 off (너무 많아서)
  gdelt: boolean;          // 기본 on
}
```

좌측 하단에 반투명 패널:
- 체크박스 + 아이콘 + 라벨 + 현재 카운트
- 예: `✅ 🚢 선박 (12,453)` / `✅ ✈️ 항공기 (4,892)` / `☐ 🛰️ 위성 (2,103)`

### 3.6 수정 대상 파일

```
frontend/src/
├── components/map/
│   ├── geoJSONBuilders.ts     # 수정: +buildFlightsGeoJSON, +buildSatellitesGeoJSON, +buildGdeltGeoJSON
│   ├── MaplibreViewer.tsx     # 수정: +3 Source/Layer 세트 + 레이어 토글 props
│   └── LayerToggle.tsx        # 신규: 레이어 토글 UI 컴포넌트
├── hooks/
│   └── useDataPolling.ts      # 수정: 반환 데이터에 flights/satellites/gdelt 포함
├── types/
│   └── dashboard.ts           # 수정: +Flight, +Satellite 인터페이스
└── app/
    └── page.tsx               # 수정: activeLayers 상태 + LayerToggle + GeoJSON 빌더 호출
```

## 4. 마일스톤

- [x] **M1: 타입 정의 + GeoJSON 빌더** — dashboard.ts에 Flight, Satellite 인터페이스 추가. geoJSONBuilders.ts에 buildFlightsGeoJSON, buildSatellitesGeoJSON, buildGdeltGeoJSON 함수 추가. useDataPolling이 반환하는 데이터에서 flights/satellites/gdelt 필드 파싱.
  - 검증: 테스트 데이터 → GeoJSON FeatureCollection 변환 정상

- [x] **M2: MapLibre 레이어 추가** — MaplibreViewer.tsx에 3개 Source/Layer 세트 추가 (flights, satellites, gdelt). 각 레이어별 스타일링 (아이콘, 색상, 클러스터링). useImperativeSource로 데이터 업데이트. 클릭 팝업 (항공기: callsign/모델/고도, GDELT: 헤드라인).
  - 검증: 지도에 항공기/위성/GDELT 이벤트 표시

- [x] **M3: 레이어 토글 UI** — LayerToggle.tsx 컴포넌트. activeLayers 상태 관리 (page.tsx). 각 레이어 on/off + 현재 카운트 표시. 위성은 기본 off (성능 고려).
  - 검증: 토글 클릭 → 레이어 표시/숨김 동작

- [x] **M4: 빌드 검증** — `npm run build` 성공. 전체 레이어 동시 표시 시 성능 확인.
  - 검증: TypeScript 에러 0, 빌드 성공

## 5. 성공 기준

- 항공기(상업/군용)가 지도에 표시되고 heading 방향으로 회전한다
- 위성이 지도에 작은 마커로 표시된다
- GDELT 분쟁 이벤트가 색상 코딩된 마커로 표시되고 클릭 시 헤드라인이 보인다
- 각 레이어를 개별적으로 on/off 토글할 수 있다
- 기존 선박 레이어와 시뮬레이션 오버레이가 정상 동작한다 (regression 없음)
- 백엔드 변경 없이 프론트엔드만으로 구현된다

## 6. 위험 및 완화

| 위험 | 완화 |
|------|------|
| 5,000+ 항공기 + 2,000+ 위성 동시 렌더링 성능 | 클러스터링 적극 활용. 위성은 기본 off. viewport culling (inView 필터) |
| SB 데이터 필드명이 예상과 다를 수 있음 | PRD 3에서 탐색한 SB 데이터 구조 참조. 구현 전 실제 응답 확인 |
| 레이어가 너무 많아 시각적 혼잡 | 기본 off 레이어(위성) 분리. 레이어별 opacity 조절 |

## 7. 참고

### 관련 PRD
- **PRD 2 (shadowbroker-integration)** — OSINT 프록시가 이미 전체 데이터 전달
- **PRD 6a (frontend-foundation)** — MapLibre + useDataPolling + useImperativeSource 패턴
- **PRD 3 (seed-generation)** — ShadowBroker 데이터 구조 탐색 결과 (ship/flight/satellite 필드)

### ShadowBroker 데이터 볼륨 (SPEC §21)
- ~5,000 항공기 (60초마다 갱신)
- ~25,000 선박 (실시간 WebSocket)
- ~2,000 위성 (60초마다 갱신)
- ~1,000 GDELT 이벤트 (6시간마다)

### 좌표 필드명 주의 (AGENTS.md)
- Ships/flights/satellites: `lng` 사용
- GDELT: GeoJSON `geometry.coordinates[0]` (lng)

## 진행 로그

| 날짜 | 상태 | 내용 |
|------|------|------|
| 2026-03-20 | Draft | v2 로드맵 첫 PRD 작성 |
