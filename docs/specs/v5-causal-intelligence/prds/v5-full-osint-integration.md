# PRD: 전체 OSINT 피드 통합 + 상황 인식 패널

> Status: Complete
> Created: 2026-03-22
> Dependencies: multi-feed-integration, frontend-foundation, shadowbroker-integration, seed-generation
> 관련 스펙: `specs/MVP-SPEC.md` Section 14 (v2 로드맵), Section 18 (Action Layer)
> 버전: v5.0

---

## 1. 문제 정의

ShadowBroker는 27개 OSINT 데이터 소스를 제공하지만, 현재 osint-simulator는 이 중 11개만 시드 생성에, 5개만 프론트엔드에 활용한다. 나머지 16개는 API를 통해 이미 전달되고 있으나 파싱·시각화·분석 파이프라인에서 완전히 무시된다.

또한 프론트엔드에 OSINT 데이터의 **맥락적 해석**(어떤 자산이 어디에 있고, 왜 의미 있는지)을 보여주는 UI가 없다. ShadowBroker 대시보드는 왼쪽 패널에서 실시간 상황 브리핑을 제공하지만, osint-simulator에는 이에 대응하는 UI가 없어 분석관이 데이터의 의미를 스스로 해석해야 한다.

### 현황 요약

| 영역 | 전체 | 사용 중 | 미사용 |
|------|-----|--------|-------|
| 시드 생성 (백엔드) | 27 | 11 | 16 |
| 프론트엔드 지도 레이어 | 27 | 4 (ships, flights, satellites, bases) | 23 |
| 프론트엔드 데이터 폴링 | 27 | 5 (ships, flights, satellites, bases, gdelt) | 22 |
| 상황 인식 패널 | — | 없음 | — |

## 2. 솔루션 개요

두 트랙으로 진행한다:

**트랙 A: 전체 OSINT 피드 통합** — 미사용 16개 데이터 소스를 시드 생성 + 프론트엔드에 통합
**트랙 B: OSINT 상황 패널** — 좌측 사이드바에 실시간 상황 브리핑 UI 추가

```
┌──────────────┐┌──────────────────────────────┐┌──────────────┐
│ OSINT 패널   ││            MAP               ││ SIMULATION   │
│ (신규, 좌측) ││                              ││ PANEL (기존) │
│              ││                              ││              │
│ ● 상황 요약  ││  + 추가 레이어:              ││              │
│ ● 자산 현황  ││    UAV, CCTV, KiwiSDR,       ││              │
│ ● OSINT 피드 ││    지진, 발전소, 데이터센터,  ││              │
│ ● 데이터 선도 ││   인터넷 장애, 화재, 전선,   ││              │
│              ││    GPS 재밍 ...              ││              │
│              ││                              ││              │
└──────────────┘└──────────────────────────────┘└──────────────┘
     400px              나머지                      400px (기존)
```

## 3. 트랙 A: 전체 OSINT 피드 통합

### 3.1 백엔드 — 시드 생성 확장

`seed_generator.py`에 미사용 데이터 소스별 `_summarize_*` 메서드를 추가하고, `_collect_and_summarize`에서 호출한다.

#### 추가 대상 (우선순위순)

**🔴 즉시 (군사·지정학 직접 관련)**

| 데이터 소스 | 메서드 | LLM 프롬프트 섹션 | 요약 내용 |
|------------|--------|-------------------|----------|
| `military_bases` | `_summarize_military_bases` | `## 군사 기지 배치` | 국가별 기지 수, 군종(해군/공군/육군), 주요 기지명 |
| `uavs` | `_summarize_uavs` | `## 무인기(UAV) 활동` | UAV 유형(HALE/MALE), 국가별 대수, 모델(RQ-4, MQ-9 등) |
| `tracked_flights` | (기존 military_flights 머지 활용, 시드 프롬프트에 별도 섹션 추가) | `## 특별 추적 항공기` | AF1/Marine One 등 VIP 항공기, 정부 전용기 동선 |

**🟡 높은 가치 (간접 지표)**

| 데이터 소스 | 메서드 | LLM 프롬프트 섹션 | 요약 내용 |
|------------|--------|-------------------|----------|
| `private_jets` | `_summarize_private_jets` | 기존 `osint_signals`에 병합 | 방산 CEO/올리가르히 의심 동선 (Plane-Alert DB 매칭 시) |
| `kiwisdr` | `_summarize_kiwisdr` | 기존 `osint_signals`에 병합 | 해역 내 HF 수신기 수, SIGINT 가용성 |
| `power_plants` | `_summarize_power_plants` | 기존 `osint_signals`에 병합 | 해역 인근 핵발전소/대형 발전소 (분쟁 시 타겟) |
| `datacenters` | `_summarize_datacenters` | 기존 `osint_signals`에 병합 | 해역 인근 주요 데이터센터 (사이버전 맥락) |
| `earthquakes` | `_summarize_earthquakes` | 기존 `osint_signals`에 병합 | 규모 4.0+ 지진 발생 시 군사 재배치/인도적 위기 트리거 |

**🟢 상황적 (맥락 보강)**

| 데이터 소스 | 메서드 | 처리 | 이유 |
|------------|--------|------|------|
| `space_weather` | `_summarize_space_weather` | `osint_signals` 병합 | Kp ≥ 5 (STORM) 시에만 포함 — 위성·통신 교란 |
| `airports` | 시드에 불포함 | — | 참조 데이터 (항공편 출발지/도착지 조회용). 프론트엔드만 활용 |
| `cctv` | 시드에 불포함 | — | 도시 감시 카메라. 해양 지정학 시나리오에 기여 미미 |
| `commercial_flights` | 시드에 불포함 | — | 민간 항공 = 노이즈. 단, 항로 우회/금지구역 감지 로직은 향후 검토 |
| `private_flights` | 시드에 불포함 | — | 일반 경비행기. 분석 가치 낮음 |
| `weather` | 시드에 불포함 | — | 레이더 타일 메타데이터만 제공. 프론트엔드 시각화만 활용 |
| `traffic` | 시드에 불포함 | — | 도로 교통. 지정학 무관 |
| `oil` | 이미 포함 | — | `stocks` 요약에 WTI/Brent 포함됨 |

#### 시드 프롬프트 확장

현재 `SEED_GENERATION_PROMPT`에 3개 섹션을 추가한다:

```python
SEED_GENERATION_PROMPT = """\
...
## 군함 배치 현황
{vessel_deployment}

## 군사 기지 배치                    ← 신규
{military_bases}

## 군용 항공기 활동
{military_flights}

## 특별 추적 항공기 (VIP/정부 전용기)  ← 신규
{tracked_flights}

## 무인기(UAV) 활동                  ← 신규
{uav_activity}

## 정찰/감시 위성 활동
{satellite_activity}

## GDELT 분쟁 이벤트 (최근)
{gdelt_context}

## 실시간 OSINT 정보
{osint_signals}
...
"""
```

### 3.2 프론트엔드 — 데이터 폴링 확장

`useDataPolling.ts`에서 현재 5개 필드만 파싱하고 나머지를 버린다. SB API 응답의 전체 필드를 파싱하도록 확장한다.

#### 타입 정의 추가 (`types/dashboard.ts`)

```typescript
// 신규 타입
interface UAV {
  callsign: string;
  country: string;
  lat: number;
  lng: number;
  alt: number;
  uav_type: string;        // HALE | MALE
  aircraft_model: string;  // RQ-4, MQ-9, TB2 등
}

interface CCTV {
  camera_id: string;
  lat: number;
  lon: number;             // ⚠️ AGENTS.md: CCTV는 lon 사용
  location_name: string;
  country: string;
}

interface KiwiSDR {
  node_id: string;
  lat: number;
  lon: number;             // ⚠️ AGENTS.md: KiwiSDR는 lon 사용
  location_name: string;
}

interface Earthquake {
  id: string;
  mag: number;
  lat: number;
  lng: number;
  place: string;
}

interface PowerPlant {
  name: string;
  country: string;
  fuel_type: string;
  capacity_mw: number;
  lat: number;
  lng: number;
}

interface Datacenter {
  name: string;
  company: string;
  country: string;
  lat: number;
  lng: number;
}

interface GPSJamming {
  lat: number;
  lng: number;
  severity: number;
  affected_count: number;
}

interface InternetOutage {
  region_name: string;
  country_name: string;
  severity: number;
  lat: number;
  lng: number;
}

interface FIRMSFire {
  lat: number;
  lng: number;
  frp: number;
  confidence: string;
}

interface SpaceWeather {
  kp_index: number;
  kp_text: string;       // QUIET | UNSETTLED | ACTIVE | STORM
  events: Array<{
    type: string;
    begin: string;
    end: string;
  }>;
}

// 통합 인터페이스
interface LiveDataFast {
  ships: Ship[];
  commercial_flights: Flight[];
  military_flights: Flight[];
  private_flights: Flight[];
  private_jets: Flight[];
  tracked_flights: Flight[];
  satellites: Satellite[];
  cctv: CCTV[];
  uavs: UAV[];
  liveuamap: unknown[];
  gps_jamming: GPSJamming[];
  freshness: Record<string, string>;
}

interface LiveDataSlow {
  news: unknown[];
  stocks: unknown[];
  oil: unknown;
  weather: unknown;
  earthquakes: Earthquake[];
  gdelt: unknown[];
  airports: unknown[];
  kiwisdr: KiwiSDR[];
  space_weather: SpaceWeather | null;
  internet_outages: InternetOutage[];
  firms_fires: FIRMSFire[];
  datacenters: Datacenter[];
  military_bases: MilitaryBase[];
  power_plants: PowerPlant[];
  frontlines: unknown;
  freshness: Record<string, string>;
}
```

#### 좌표 필드명 주의 (AGENTS.md)

| 데이터 소스 | 경도 필드 |
|------------|----------|
| ships, flights, satellites, uavs, earthquakes, gps_jamming, fires, power_plants, datacenters | `lng` |
| cctv, kiwisdr | `lon` |

GeoJSON 빌더에서 소스별로 올바른 필드명을 사용해야 한다. **통일 금지** — SB 내부 뷰포트 필터링이 깨진다.

### 3.3 프론트엔드 — 지도 레이어 추가

현재 4개 레이어(ships, flights, satellites, bases)에 추가 레이어를 등록한다.

#### 레이어 카테고리 + 색상 체계

| 카테고리 | 레이어 | 색상 | 기본 표시 | 아이콘/형태 |
|---------|--------|------|---------|------------|
| **군사** | ships | `#22d3ee` (cyan) | ✅ ON | 삼각형 (heading 방향) |
| | military_flights | `#f97316` (orange) | ✅ ON | 원형 |
| | satellites | `#a855f7` (purple) | ✅ ON | 작은 원형 |
| | military_bases | `#ef4444` (red) | ✅ ON | 사각형 |
| | uavs | `#eab308` (yellow) | ✅ ON | 다이아몬드 |
| | tracked_flights | `#ec4899` (pink) | ✅ ON | 별형 |
| **인프라** | power_plants | `#f59e0b` (amber) | ❌ OFF | 원형 |
| | datacenters | `#6366f1` (indigo) | ❌ OFF | 사각형 |
| | cctv | `#78716c` (stone) | ❌ OFF | 점 |
| **SIGINT** | kiwisdr | `#14b8a6` (teal) | ❌ OFF | 원형 |
| | gps_jamming | `#dc2626` (red, 펄스) | ✅ ON | 펄스 원형 |
| **환경** | earthquakes | `#b91c1c` (dark red) | ❌ OFF | 원형 (규모 비례) |
| | firms_fires | `#ea580c` (orange-red) | ❌ OFF | 히트맵 |
| **정보** | gdelt | `#f97316` (orange) | ❌ OFF | 클러스터 원형 |
| | internet_outages | `#7c3aed` (violet) | ❌ OFF | 원형 (심각도 비례) |
| | frontlines | `#dc2626` (red) | ❌ OFF | 라인 |
| | news | — | — | 지도 레이어 아님 (패널 전용) |
| | stocks/oil | — | — | 지도 레이어 아님 (패널 전용) |
| | weather | — | — | 타일 오버레이 (향후) |
| | space_weather | — | — | 지도 레이어 아님 (패널 전용) |

#### LayerToggle 확장

현재 4개 토글에서 카테고리별 그룹 토글로 확장한다:

```
┌─────────────────────┐
│ 🎯 군사              │ ← 카테고리 토글 (전체 on/off)
│  ☑ 선박 (234)       │
│  ☑ 군용기 (47)      │
│  ☑ UAV (12)         │
│  ☑ 추적기 (3)       │
│  ☑ 위성 (89)        │
│  ☑ 기지 (15)        │
│  ☑ GPS 재밍 (2)     │
│                     │
│ 🏭 인프라            │
│  ☐ 발전소 (8)       │
│  ☐ 데이터센터 (5)   │
│  ☐ CCTV (23)        │
│                     │
│ 📡 SIGINT            │
│  ☐ KiwiSDR (7)      │
│                     │
│ 🌍 환경              │
│  ☐ 지진 (3)         │
│  ☐ 화재 (15)        │
│                     │
│ 📰 정보              │
│  ☐ GDELT (156)      │
│  ☐ 인터넷 장애 (4)  │
│  ☐ 전선 (—)         │
└─────────────────────┘
```

## 4. 트랙 B: OSINT 상황 패널 (좌측 사이드바)

기존 SimulationPanel은 우측 400px를 차지한다. OSINT 상황 패널은 좌측에 배치하여 **OSINT 데이터 ↔ 시뮬레이션 제어** 의 대칭 레이아웃을 구성한다.

### 4.1 패널 구조

```
┌─────────────────────────────────┐
│ OSINT SITUATION          [×]   │ ← 헤더 + 닫기
│─────────────────────────────────│
│ [요약] [자산] [피드] [선도]      │ ← 탭 네비게이션
│─────────────────────────────────│
│                                 │
│  (탭별 콘텐츠, 스크롤)           │
│                                 │
└─────────────────────────────────┘
  400px, position: fixed, left: 0
  height: 100vh
  zIndex: 20 (SimulationPanel과 동일)
  collapsible (토글 버튼: 좌하단)
```

### 4.2 탭 상세

#### 탭 1: 상황 요약 (Overview)

실시간 OSINT 데이터를 종합한 한눈 요약. 지도를 안 봐도 현재 상황을 파악할 수 있어야 한다.

```
┌─────────────────────────────────┐
│ 📊 상황 요약                     │
│                                 │
│ ┌─ 긴장도 ─────────────────────┐│
│ │ ██████████░░░░░ 6.7 / 10     ││ ← GDELT tension_score 기반
│ │ 24시간 전 대비: ▲ +0.8       ││
│ └──────────────────────────────┘│
│                                 │
│ ┌─ 자산 현황 ──────────────────┐│
│ │ 🚢 군함 12척 (CN 5, US 4, ..)││
│ │ ✈️ 군용기 47대               ││
│ │ 🛸 UAV 8대                   ││
│ │ 🛰️ 정찰위성 23기 (통과 중)   ││
│ │ 🏗️ 군사기지 15개             ││
│ │ ⚡ GPS 재밍 2건              ││
│ └──────────────────────────────┘│
│                                 │
│ ┌─ 최근 이벤트 (5건) ──────────┐│
│ │ 12:34 GDELT: 남중국해 해군...││
│ │ 12:20 뉴스: BBC — 대만 해협..││
│ │ 11:55 화재: FRP 85MW 감지    ││
│ │ 11:30 인터넷: 필리핀 장애 72%││
│ │ 11:15 지진: M4.2 대만 동부   ││
│ └──────────────────────────────┘│
│                                 │
│ ┌─ 경제 지표 ──────────────────┐│
│ │ RTX +2.3%  LMT +1.8%        ││
│ │ WTI $78.4 (+0.5%)            ││
│ └──────────────────────────────┘│
│                                 │
│ 마지막 갱신: 12:35:22 UTC       │
└─────────────────────────────────┘
```

#### 탭 2: 자산 현황 (Assets)

뷰포트 내 군사 자산을 국가별·유형별로 분류한 상세 목록. 클릭 시 지도에서 해당 자산으로 이동(flyTo).

```
┌─────────────────────────────────┐
│ 🎯 자산 현황                     │
│                                 │
│ ▾ 🇨🇳 중국 (18)                 │ ← 접이식
│   🚢 군함 5척                   │
│     Type 055 구축함 × 2         │
│     Type 052D 구축함 × 2        │
│     Liaoning 항공모함 × 1       │
│   ✈️ 군용기 8대                 │
│     J-16 × 4, H-6K × 2 ...    │
│   🛸 UAV 3대                   │
│     BZK-005 × 2, WZ-7 × 1     │
│   🏗️ 기지 2개                  │
│     Yulin Naval Base            │
│     Woody Island                │
│                                 │
│ ▾ 🇺🇸 미국 (14)                 │
│   🚢 군함 4척                   │
│     Arleigh Burke × 2           │
│     Nimitz 항공모함 × 1         │
│     Ticonderoga 순양함 × 1     │
│   ✈️ 군용기 12대                │
│   🛸 UAV 2대                   │
│     RQ-4 Global Hawk × 1       │
│     MQ-9 Reaper × 1            │
│   ...                           │
│                                 │
│ ▾ 🛰️ 정찰 위성 (23)            │
│   🇨🇳 Yaogan-30 × 3            │
│   🇺🇸 KH-11 × 2               │
│   🇷🇺 Persona × 1              │
│   ...                           │
│                                 │
│ ▸ 🇯🇵 일본 (5)                  │
│ ▸ 🇵🇭 필리핀 (2)               │
└─────────────────────────────────┘
```

#### 탭 3: OSINT 피드 (Feed)

전체 데이터 소스의 실시간 이벤트를 시간순 역순으로 표시.

```
┌─────────────────────────────────┐
│ 📡 OSINT 피드                    │
│                                 │
│ [전체] [군사] [정보] [인프라] [환경]│ ← 필터
│                                 │
│ 12:34 📰 GDELT                  │
│ "南海 군사 대치 긴장 고조"       │
│ Goldstein: -4.2 | 기사 23건    │
│                                 │
│ 12:28 📡 GPS 재밍               │
│ 심각도 78%, 영향 항공기 15대    │
│ 위치: 16.2°N, 112.8°E          │
│                                 │
│ 12:20 📰 BBC News               │
│ "Taiwan Strait tensions rise..."│
│ Risk Score: 8.2                 │
│                                 │
│ 12:15 🔥 FIRMS                  │
│ FRP 85MW — 해남도 인근          │
│ 군사 훈련 관련 가능성           │
│                                 │
│ 12:10 🌐 인터넷 장애            │
│ 필리핀 — 심각도 72%             │
│ BGP 경로 변경 감지              │
│                                 │
│ 11:55 ✈️ 특별 추적              │
│ POTUS — AF1 이동 감지           │
│ 앤드류스 AFB → 불명             │
│                                 │
│ ... (무한 스크롤)               │
└─────────────────────────────────┘
```

#### 탭 4: 데이터 선도 (Freshness)

ShadowBroker WorldviewLeftPanel 패턴을 차용. 각 데이터 소스의 마지막 갱신 시각과 상태를 표시.

```
┌─────────────────────────────────┐
│ ⏱ 데이터 선도                    │
│                                 │
│ ─── 빠른 갱신 (15초) ─────────  │
│ ● ships         12s ago    234  │
│ ● mil_flights   12s ago     47  │
│ ● uavs          12s ago     12  │
│ ● tracked       12s ago      3  │
│ ● satellites    12s ago     89  │
│ ● cctv          12s ago     23  │
│ ● gps_jamming   12s ago      2  │
│ ● liveuamap     12s ago      8  │
│                                 │
│ ─── 느린 갱신 (2분) ──────────  │
│ ● gdelt         1m ago     156  │
│ ● news          1m ago      12  │
│ ● mil_bases     1m ago      15  │
│ ● earthquakes   1m ago       3  │
│ ● fires         1m ago      15  │
│ ● outages       1m ago       4  │
│ ● kiwisdr       1m ago       7  │
│ ● stocks        1m ago       8  │
│ ● power_plants  1m ago       8  │
│ ● datacenters   1m ago       5  │
│ ● space_wx      1m ago    QUIET │
│ ● frontlines    1m ago       —  │
│                                 │
│ ● = 정상 (< 2배 주기)          │
│ ● = 지연 (> 2배 주기)          │
│ ● = 오류/미수신                 │
└─────────────────────────────────┘
```

### 4.3 인터랙션

| 동작 | 결과 |
|------|------|
| 자산 항목 클릭 | 지도가 해당 위치로 flyTo + 팝업 표시 |
| OSINT 피드 항목 클릭 | 지도가 해당 이벤트 위치로 flyTo |
| 카테고리 헤더 클릭 | 접기/펼치기 토글 |
| 패널 닫기 (×) | 패널 숨김 + 좌하단에 열기 버튼 표시 |
| 데이터 선도 항목 hover | 해당 소스의 마지막 갱신 시각 상세 표시 |

### 4.4 데이터 흐름

```
useDataPolling (확장)
  ├── pollFast (15s) → ships, flights, uavs, tracked, satellites, cctv, gps_jamming, liveuamap
  └── pollSlow (120s) → gdelt, news, mil_bases, earthquakes, fires, outages, kiwisdr, stocks, power_plants, datacenters, space_weather, frontlines
       │
       ▼
  page.tsx (state)
       │
       ├── MaplibreViewer (GeoJSON 레이어)
       ├── LayerToggle (카테고리별 토글)
       ├── OSINTPanel (상황 요약 + 자산 + 피드 + 선도)  ← 신규
       └── SimulationPanel (기존)
```

## 5. 수정 대상 파일

### 트랙 A: 피드 통합

```
# 백엔드 수정
backend/app/services/seed_generator.py       # +5 summarize 메서드, 프롬프트 확장
                                             # _summarize_military_bases
                                             # _summarize_uavs
                                             # _summarize_tracked_flights
                                             # _summarize_private_jets
                                             # _summarize_kiwisdr
                                             # _summarize_power_plants
                                             # _summarize_datacenters
                                             # _summarize_earthquakes
                                             # _summarize_space_weather

# 프론트엔드 수정
frontend/src/types/dashboard.ts              # +12 인터페이스, LiveDataFast/Slow 확장
frontend/src/hooks/useDataPolling.ts         # 전체 필드 파싱
frontend/src/components/map/geoJSONBuilders.ts  # +10 GeoJSON 빌더 함수
frontend/src/components/map/MaplibreViewer.tsx  # +10 Source/Layer, 팝업 확장
frontend/src/components/map/LayerToggle.tsx  # 카테고리 그룹 토글로 리팩토링
frontend/src/app/page.tsx                    # 추가 상태 + props 전달
```

### 트랙 B: OSINT 패널

```
# 신규
frontend/src/components/osint/OSINTPanel.tsx         # 메인 패널 컨테이너
frontend/src/components/osint/OverviewTab.tsx        # 상황 요약 탭
frontend/src/components/osint/AssetsTab.tsx          # 자산 현황 탭
frontend/src/components/osint/FeedTab.tsx            # OSINT 피드 탭
frontend/src/components/osint/FreshnessTab.tsx       # 데이터 선도 탭
frontend/src/hooks/useOSINTSummary.ts                # 요약 데이터 가공 훅

# 수정
frontend/src/app/page.tsx                            # OSINTPanel 추가, 레이아웃 조정
```

## 6. 마일스톤

- [x] **M1: 타입 + 폴링 확장** — `dashboard.ts`에 12개 신규 타입 추가. `useDataPolling`이 SB fast/slow 응답의 전체 필드를 파싱하여 반환.
  - 검증: `console.log`로 uavs, tracked_flights, military_bases 등 데이터 수신 확인

- [x] **M2: 시드 생성 확장** — `seed_generator.py`에 `_summarize_military_bases`, `_summarize_uavs` 등 9개 메서드 추가. `_collect_and_summarize`에서 호출. 시드 프롬프트에 3개 섹션 추가.
  - 검증: 시드 생성 시 군사기지/UAV/추적기 정보가 시드 문서에 포함됨

- [x] **M3: GeoJSON 빌더 + 지도 레이어** — `geoJSONBuilders.ts`에 10개 빌더 추가. `MaplibreViewer.tsx`에 10개 Source/Layer 등록. 팝업 확장.
  - 검증: 지도에 UAV, GPS 재밍, 발전소 등 추가 레이어 표시

- [x] **M4: 레이어 토글 리팩토링** — `LayerToggle.tsx`를 카테고리 그룹 토글로 확장. 카테고리 전체 on/off + 개별 레이어 on/off.
  - 검증: 군사/인프라/SIGINT/환경/정보 카테고리별 토글 동작

- [x] **M5: OSINT 상황 패널 — 기본 구조** — `OSINTPanel.tsx` + 4개 탭 컴포넌트 생성. 좌측 400px 고정, 접이식. page.tsx에 통합.
  - 검증: 좌측 패널 열기/닫기, 4개 탭 전환 동작

- [x] **M6: 상황 요약 + 자산 탭** — `OverviewTab`, `AssetsTab` 구현. 긴장도 게이지, 자산 국가별 분류, flyTo 연동.
  - 검증: 자산 항목 클릭 → 지도 이동, 긴장도 수치 표시

- [x] **M7: 피드 + 선도 탭** — `FeedTab`, `FreshnessTab` 구현. 실시간 이벤트 스트림, 데이터 소스별 선도 표시.
  - 검증: 피드 필터링, 선도 상태 표시 (정상/지연/오류)

- [x] **M8: 빌드 검증 + 성능** — `npm run build` 성공. 전체 레이어 + 패널 동시 동작 시 성능 확인.
  - 검증: TypeScript 에러 0, 빌드 성공, FPS ≥ 30 (20개 레이어 활성 시)

## 7. 성공 기준

- ShadowBroker가 제공하는 27개 데이터 소스 중 적어도 20개가 프론트엔드에서 시각화된다
- 시드 생성 시 military_bases, uavs, tracked_flights가 시드 문서에 포함된다
- 좌측 OSINT 패널에서 현재 상황을 한눈에 파악할 수 있다
- 자산 항목 클릭 → 지도 flyTo가 동작한다
- 데이터 선도 탭에서 각 소스의 갱신 상태를 확인할 수 있다
- 기존 SimulationPanel이 정상 동작한다 (regression 없음)
- 전체 레이어 활성 시 FPS ≥ 30

## 8. 위험 및 완화

| 위험 | 완화 |
|------|------|
| 20+ 레이어 동시 렌더링 성능 | 군사 카테고리만 기본 ON. 나머지 OFF. viewport culling. 클러스터링 적극 활용 |
| OSINT 패널 + SimulationPanel 동시 표시 시 지도 영역 부족 | 양쪽 패널 독립적 접이식. 동시 열기 시 지도 최소 폭 보장 (600px) |
| SB 데이터 필드명 소스별 차이 (lng vs lon) | AGENTS.md 지뢰 문서화. GeoJSON 빌더에서 소스별 경도 필드 분기 |
| 시드 프롬프트 토큰 증가 (추가 섹션) | 데이터 없는 섹션은 "(미감지)" 한 줄로 축약. max_tokens 유지 |
| 긴장도 수치의 정확도 | GDELT tension_score는 참고 지표. "AI 추정치" 라벨 명시 |

## 9. 참고

### 관련 PRD
- **multi-feed-integration** — 기존 다중 피드 PRD (4개 레이어 추가). 본 PRD가 이를 대체·확장
- **frontend-foundation** — MapLibre + useDataPolling + useImperativeSource 패턴
- **seed-generation** — SeedGenerator 아키텍처
- **shadowbroker-integration** — OSINT 프록시 라우트

### ShadowBroker UI 참조
- `WorldviewLeftPanel.tsx` — 레이어 토글 + 데이터 선도 + 시스템 상태
- `NewsFeed.tsx` — 상세 상황 브리핑 (지역 도시에, 엔티티 상세)
- 패턴: 카테고리별 접이식 그룹, 아이콘 + 카운트, 색상 코딩

## 진행 로그

| 날짜 | 상태 | 내용 |
|------|------|------|
| 2026-03-22 | Draft | 전체 OSINT 통합 + 상황 패널 PRD 초안 작성 |
| 2026-03-22 | Complete | M1-M8 전체 구현. 타입+폴링 확장, 시드 생성 확장, GeoJSON+레이어, 카테고리 토글, OSINT 패널 4탭, 빌드 검증 |
