# PRD: OSINT 시계열 분석

> Status: Draft
> Created: 2026-03-22
> Dependencies: v5-full-osint-integration, v6-quality-performance (권장)
> 버전: v6.0

---

## 1. 문제 정의

OSINT 데이터가 매 15초/2분마다 폴링되지만, **현재 상태만 표시**하고 시간에 따른 변화를 보여주지 않는다. 분석관이 "지난 24시간간 이 해역의 군함 수가 어떻게 변했나?", "긴장도가 언제 급등했나?", "이 패턴이 비정상인가?" 같은 질문에 답할 수 없다.

### 현황

| 역량 | 현재 상태 | 필요 |
|------|----------|------|
| 시계열 데이터 저장 | observations 테이블에 다중 스냅샷 가능 (observed_at) | ✅ 기반 존재 |
| 시계열 집계 | 없음 — raw 데이터만 | ❌ 시간 버킷 집계 필요 |
| 트렌드 시각화 | 없음 | ❌ 차트 UI 필요 |
| 이상 탐지 | TensionAnalyzer (시뮬레이션 전용) | ❌ OSINT 실시간 이상 탐지 필요 |
| 데이터 보존 | 무기한 (삭제 없음) | ❌ TTL/보존 정책 필요 |

## 2. 솔루션 개요

3개 트랙:

**트랙 A: 시계열 데이터 레이어** — 시간 버킷 집계 테이블 + 주기적 집계 + 보존 정책
**트랙 B: 분석 API** — 트렌드 조회, 이상 탐지, 비교 분석 엔드포인트
**트랙 C: 시각화** — 시계열 차트 (lightweight-charts) + OSINT 패널 통합

```
┌──────────────────────────────────────────────────────┐
│ OSINT 패널 (좌측)                                     │
│ ┌─ [요약] [자산] [피드] [선도] [트렌드] ─┐ ← 신규 탭   │
│ │                                       │            │
│ │  📈 자산 추이 (24h)                    │            │
│ │  ┌────────────────────┐               │            │
│ │  │   12  __/\__       │ 군함          │            │
│ │  │   8  /      \__    │ 군용기         │            │
│ │  │   4                │ UAV           │            │
│ │  │   0 ──────────────│               │            │
│ │  │   00:00    12:00   │               │            │
│ │  └────────────────────┘               │            │
│ │                                       │            │
│ │  ⚠️ 이상 탐지                          │            │
│ │  🔴 군함 +5척 (2h 내) — 비정상         │            │
│ │  🟡 GPS 재밍 신규 감지                  │            │
│ │                                       │            │
│ │  📊 긴장도 추이 (7d)                    │            │
│ │  ┌────────────────────┐               │            │
│ │  │  7 ────────/\──    │               │            │
│ │  │  5 ───/\──/  \──  │               │            │
│ │  │  3 ──/             │               │            │
│ │  └────────────────────┘               │            │
│ └───────────────────────────────────────┘            │
└──────────────────────────────────────────────────────┘
```

## 3. 트랙 A: 시계열 데이터 레이어

### 3.1 시간 버킷 집계 테이블

observations 테이블은 이미 다중 스냅샷을 지원한다 (같은 source_id에 여러 observed_at). 하지만 매 요청마다 raw 데이터를 집계하면 느리다. 사전 집계 테이블을 추가한다.

```sql
CREATE TABLE osint_metrics_hourly (
    id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,       -- ships, military_flights, satellites, uavs, ...
    bucket_hour TEXT NOT NULL,       -- "2026-03-22T14:00:00Z" (시간 단위 버킷)
    region_name TEXT,                -- nullable (전체 또는 특정 지역)
    count INTEGER NOT NULL,          -- 해당 시간의 고유 엔티티 수
    country_breakdown TEXT,          -- JSON: {"CN": 5, "US": 4, "JP": 2}
    metadata TEXT,                   -- JSON: 추가 메트릭 (평균 속도, 최대 고도 등)
    created_at TEXT NOT NULL
);
CREATE INDEX idx_osint_metrics_source_hour ON osint_metrics_hourly(source_type, bucket_hour);
CREATE INDEX idx_osint_metrics_region ON osint_metrics_hourly(region_name, bucket_hour);
```

### 3.2 집계 스케줄러

매 시간 실행되는 백그라운드 태스크가 observations + ShadowBroker 폴링 데이터를 집계하여 osint_metrics_hourly에 저장.

```python
class MetricsAggregator:
    async def aggregate_hourly(self, hour: str, region_name: str | None = None):
        # 1. observations 테이블에서 해당 시간 + 지역의 데이터 집계
        # 2. source_type별 고유 source_id 카운트
        # 3. 국가별 분포 계산
        # 4. osint_metrics_hourly에 UPSERT
```

### 3.3 OSINT 스냅샷 히스토리

현재 scenario_snapshots는 시나리오당 1개만 저장. 시계열 분석을 위해 주기적 스냅샷을 별도 저장.

```sql
CREATE TABLE osint_snapshots (
    id TEXT PRIMARY KEY,
    snapshot_at TEXT NOT NULL,
    region_bbox TEXT,                -- nullable (전체 뷰포트)
    asset_counts TEXT NOT NULL,      -- JSON: {"ships": 234, "military_flights": 47, ...}
    tension_indicators TEXT,         -- JSON: {"gdelt_avg": 4.2, "gps_jamming": 2, ...}
    created_at TEXT NOT NULL
);
CREATE INDEX idx_osint_snapshots_time ON osint_snapshots(snapshot_at);
```

### 3.4 보존 정책

| 데이터 | 보존 기간 | 삭제 주기 |
|--------|----------|----------|
| observations (raw) | 7일 | 매일 자정 |
| osint_metrics_hourly | 90일 | 매주 |
| osint_snapshots | 30일 | 매주 |

### 3.5 인덱스 추가

```sql
CREATE INDEX idx_obs_source_time ON observations(source_type, source_id, observed_at);
CREATE INDEX idx_obs_time_range ON observations(observed_at);
```

## 4. 트랙 B: 분석 API

### 4.1 트렌드 조회

```
GET /api/analytics/trend?source_type=ships&hours=24&interval=1h&region=south_china_sea
→ {
    "source_type": "ships",
    "interval": "1h",
    "data_points": [
        {"time": "2026-03-22T00:00:00Z", "count": 8, "countries": {"CN": 3, "US": 2, ...}},
        {"time": "2026-03-22T01:00:00Z", "count": 10, ...},
        ...
    ],
    "summary": {"min": 8, "max": 15, "avg": 11.2, "trend": "increasing"}
}
```

### 4.2 이상 탐지

```
GET /api/analytics/anomalies?hours=24&region=south_china_sea
→ {
    "anomalies": [
        {
            "type": "asset_surge",
            "source_type": "ships",
            "detected_at": "2026-03-22T14:00:00Z",
            "severity": "high",
            "detail": "군함 +5척 (2시간 내). 평균 대비 2.3σ",
            "current": 15,
            "baseline": 8,
            "sigma": 2.3
        },
        {
            "type": "new_signal",
            "source_type": "gps_jamming",
            "detected_at": "2026-03-22T13:30:00Z",
            "severity": "medium",
            "detail": "신규 GPS 재밍 감지",
            "current": 1,
            "baseline": 0
        }
    ]
}
```

이상 탐지 알고리즘:
- **asset_surge**: 최근 2시간 카운트가 7일 평균 대비 2σ 초과
- **asset_departure**: 기존 자산 대량 이탈 (카운트 50% 이상 감소)
- **new_signal**: 기존에 없던 데이터 소스 감지 (GPS 재밍, 인터넷 장애 등)
- **tension_spike**: GDELT 긴장도가 7일 이동평균 대비 1.5σ 초과

### 4.3 비교 분석

```
GET /api/analytics/compare?source_type=ships&period_a=2026-03-15&period_b=2026-03-22&hours=24
→ {
    "period_a": {"avg": 8.3, "max": 12, "trend": "stable"},
    "period_b": {"avg": 12.7, "max": 18, "trend": "increasing"},
    "delta": {"avg": +4.4, "max": +6, "pct_change": "+53%"}
}
```

### 4.4 수정 대상 파일

```
# 신규
backend/app/services/metrics_aggregator.py     # 시간 버킷 집계
backend/app/services/anomaly_detector.py       # 이상 탐지 (σ 기반)
backend/app/routers/analytics.py               # 트렌드/이상/비교 API
backend/app/tasks/aggregation_scheduler.py     # 주기적 집계 스케줄러

# 수정
backend/app/database.py                        # 3개 신규 테이블 + 2개 인덱스
backend/app/main.py                            # analytics 라우터 등록 + 스케줄러 시작
```

## 5. 트랙 C: 시각화

### 5.1 차트 라이브러리

**Primary**: `lightweight-charts` (TradingView) — 35KB gzip, Canvas 기반, 내장 줌/팬/크로스헤어, 실시간 update(), 다크 테마 지원. `dynamic({ ssr: false })` — MapLibre와 동일 패턴.

**Secondary**: `recharts` — 정적/요약 차트 (막대 그래프, 비교). SSR 지원.

### 5.2 트렌드 탭 (OSINTPanel 5번째 탭)

OSINTPanel에 "트렌드" 탭 추가:

```
┌─────────────────────────────────────┐
│ 📈 트렌드                            │
│                                     │
│ [기간] [24h] [7d] [30d]             │ ← 기간 선택
│ [소스] [전체▾]                       │ ← 소스 필터
│                                     │
│ ┌─ 자산 추이 ──────────────────────┐│
│ │  lightweight-charts 라인 차트     ││
│ │  - 선박 (cyan)                   ││
│ │  - 군용기 (orange)               ││
│ │  - UAV (yellow)                  ││
│ │  - 위성 (purple)                 ││
│ │  줌/팬/크로스헤어 내장            ││
│ └──────────────────────────────────┘│
│                                     │
│ ┌─ 긴장도 추이 ────────────────────┐│
│ │  lightweight-charts 에어리어 차트  ││
│ │  - GDELT tension_score (red)     ││
│ │  - 이상 구간 하이라이트 (red bg)   ││
│ └──────────────────────────────────┘│
│                                     │
│ ┌─ 이상 탐지 ──────────────────────┐│
│ │  🔴 HIGH: 군함 +5척 (2h 내)     ││
│ │       평균 대비 2.3σ, 14:00 UTC  ││
│ │  🟡 MED: GPS 재밍 신규           ││
│ │       13:30 UTC                  ││
│ │  (없음 = "현재 이상 징후 없음")    ││
│ └──────────────────────────────────┘│
│                                     │
│ ┌─ 기간 비교 ──────────────────────┐│
│ │  recharts 막대 차트              ││
│ │  이번 주 vs 저번 주              ││
│ │  선박 +53% | 군용기 +12%         ││
│ └──────────────────────────────────┘│
└─────────────────────────────────────┘
```

### 5.3 수정 대상 파일

```
# 신규
frontend/src/components/osint/TrendTab.tsx          # 트렌드 탭 메인
frontend/src/components/charts/AssetTrendChart.tsx   # 자산 추이 차트 (lightweight-charts)
frontend/src/components/charts/TensionChart.tsx      # 긴장도 차트 (lightweight-charts)
frontend/src/components/charts/PeriodCompare.tsx     # 기간 비교 (recharts)
frontend/src/components/osint/AnomalyList.tsx        # 이상 탐지 목록
frontend/src/hooks/useAnalytics.ts                   # 분석 API 호출 훅

# 수정
frontend/src/components/osint/OSINTPanel.tsx         # 트렌드 탭 추가
frontend/src/lib/gatewayApi.ts                       # 트렌드/이상/비교 API 함수
package.json                                         # lightweight-charts, recharts 추가
```

## 6. 마일스톤

- [ ] **M1: 데이터 레이어** — osint_metrics_hourly + osint_snapshots 테이블 생성. MetricsAggregator 서비스. 인덱스 추가. 보존 정책 (observations 7일 TTL).
  - 검증: 1시간 치 데이터가 osint_metrics_hourly에 집계됨

- [ ] **M2: 트렌드 API** — GET /api/analytics/trend 엔드포인트. source_type, hours, interval, region 파라미터. 시간 버킷별 카운트 + 국가 분포 반환.
  - 검증: GET /api/analytics/trend?source_type=ships&hours=24 → 24개 데이터 포인트

- [ ] **M3: 이상 탐지** — AnomalyDetector 서비스. 4가지 알고리즘 (asset_surge, asset_departure, new_signal, tension_spike). GET /api/analytics/anomalies 엔드포인트.
  - 검증: 군함 수가 2σ 초과 → anomaly 반환

- [ ] **M4: 자산 추이 차트** — lightweight-charts 설치. AssetTrendChart 컴포넌트. 자산 유형별 라인 차트 (24h/7d/30d). 줌/팬/크로스헤어.
  - 검증: OSINT 패널 트렌드 탭에서 자산 추이 차트 표시

- [ ] **M5: 긴장도 + 이상 + 비교** — TensionChart (에어리어 차트 + 이상 하이라이트). AnomalyList (심각도별 목록). PeriodCompare (recharts 막대). OSINTPanel 트렌드 탭 통합.
  - 검증: 긴장도 차트에 이상 구간 표시, 기간 비교 동작

- [ ] **M6: 집계 스케줄러 + 빌드 검증** — 매시간 자동 집계. 보존 정책 실행. npm run build 성공. 전체 트렌드 탭 동작 확인.
  - 검증: 스케줄러 실행 → metrics 집계 + 오래된 데이터 삭제

## 7. 성공 기준

- 분석관이 24시간/7일/30일 단위로 자산 추이를 차트로 확인할 수 있다
- 군함 급증, GPS 재밍 발생 등 이상 패턴이 자동 감지되어 표시된다
- 이번 주/저번 주 비교로 활동 변화를 정량적으로 파악할 수 있다
- 7일 이상 오래된 raw observations가 자동 삭제된다 (디스크 관리)
- 트렌드 API 응답이 500ms 이내이다 (사전 집계 기반)

## 8. 위험 및 완화

| 위험 | 완화 |
|------|------|
| observations 테이블 용량 폭증 | 7일 보존 정책 + 시간 버킷 집계로 raw 데이터 삭제 |
| 집계 스케줄러 실패 | 멱등성 보장 (UPSERT). 실패 시 다음 사이클에 자동 재시도 |
| lightweight-charts SSR 비호환 | dynamic({ ssr: false }) — MapLibre와 동일 패턴 |
| σ 기반 이상 탐지 오탐 | 최소 7일 베이스라인 필요. 데이터 부족 시 이상 탐지 비활성화 |
| recharts 번들 크기 (135KB) | 트렌드 탭 전체를 dynamic import로 분리 |

## 9. 기술 선택 근거

### 차트 라이브러리

| 기준 | lightweight-charts | recharts |
|------|-------------------|----------|
| 번들 | 35KB gzip | 135KB gzip |
| 용도 | 실시간 시계열 (줌/팬/크로스헤어) | 정적 비교 차트 |
| 렌더링 | Canvas (고성능) | SVG (선언적) |
| SSR | ❌ (dynamic) | ✅ 네이티브 |
| 실시간 | series.update() | React 리렌더 |

### 이상 탐지 알고리즘

통계적 이상 탐지 (Z-score 기반):
- 7일 이동평균 + 표준편차 계산
- Z-score = (현재값 - 평균) / 표준편차
- asset_surge/departure: |Z| > 2.0 → HIGH, |Z| > 1.5 → MEDIUM
- tension_spike: |Z| > 1.5 → 이상 플래그

복잡한 ML 모델 없이 통계 기반으로 시작. 오탐율이 높으면 향후 이동평균 윈도우 조정.

## 진행 로그

| 날짜 | 상태 | 내용 |
|------|------|------|
| 2026-03-22 | Draft | 코드베이스 감사 기반 시계열 분석 PRD 초안 작성 |
