# PRD: 분석관 워크스페이스

> Status: Draft
> Created: 2026-03-21
> Dependencies: scenario-management-ui, simulation-visualization
> 관련 스펙: `specs/V4-SPEC.md` PRD V4-5
> 버전: v4.0

---

## 1. 문제 정의

시나리오 검색/필터/비교가 없다. ScenarioList는 플랫 목록만 표시하며, 100개 이상의 시나리오를 관리할 수 없다. 두 시뮬레이션의 결과를 나란히 비교할 수 없다.

## 2. 솔루션 개요

- **검색 + 필터** — 시나리오 이름, 지역, 상태, 날짜 범위로 검색/필터
- **비교 뷰** — 2개 시뮬레이션을 나란히 비교 (타임라인, 행위자 상태, 지정학 결과)
- **대시보드** — 전체 시나리오 현황 (실행 중/완료/실패, 지역별 분포, 최근 활동)

## 3. 기술 상세

### 3.1 검색/필터 API

```
GET /api/scenario?q=남중국해&status=completed&region=south_china_sea
    &created_after=2026-03-01&created_before=2026-03-31
    &sort=created_at&order=desc&limit=20&offset=0
→ { scenarios: [...], total: 45 }
```

### 3.2 비교 API

```
GET /api/scenario/{id1}/compare/{id2}
→ {
    scenario_a: { name, actors, action_count, tension_avg, ... },
    scenario_b: { name, actors, action_count, tension_avg, ... },
    diff: {
        actors_added: [...],
        actors_removed: [...],
        tension_delta: 0.15,
        action_count_delta: -23,
        geopolitics_events_delta: 5
    }
}
```

### 3.3 대시보드 API

```
GET /api/dashboard
→ {
    total_scenarios: 156,
    by_status: { completed: 120, running: 3, failed: 8, created: 25 },
    by_region: { "South China Sea": 45, "Taiwan Strait": 23, ... },
    recent_activity: [{ scenario_id, action, timestamp }, ...],
    running_simulations: [{ id, name, progress, eta }, ...]
}
```

### 3.4 수정 대상 파일

```
# 신규
backend/app/services/scenario_comparator.py    # 시나리오 비교 서비스
backend/app/routers/dashboard.py               # 대시보드 API
frontend/src/components/simulation/ComparisonView.tsx  # 비교 뷰
frontend/src/components/simulation/AnalystDashboard.tsx  # 대시보드
frontend/src/components/simulation/ScenarioSearch.tsx    # 검색/필터 UI

# 수정
backend/app/routers/scenario.py                # 검색/필터 파라미터 추가
frontend/src/components/simulation/ScenarioList.tsx  # 검색/필터 통합
frontend/src/components/simulation/SimulationPanel.tsx  # 대시보드/비교 탭
```

## 4. 마일스톤

- [ ] **M1: 검색/필터 API** — GET /api/scenario에 q, status, region, created_after/before, sort, order 파라미터 추가. 전문 검색 (ILIKE). total 카운트 반환. 페이지네이션.
  - 검증: GET /api/scenario?q=남중국해&status=completed → 필터된 결과 + total

- [ ] **M2: 비교 API** — GET /api/scenario/{id1}/compare/{id2} 엔드포인트. 행위자, 액션, 긴장도, 지정학 이벤트 diff 계산.
  - 검증: 2개 완료된 시나리오 비교 → diff 데이터 반환

- [ ] **M3: 프론트엔드 검색/필터 UI** — ScenarioList 상단에 검색 바 + 필터 드롭다운 (상태, 지역). 실시간 검색 (debounce 300ms). 정렬 옵션.
  - 검증: "남중국해" 검색 → 관련 시나리오만 표시

- [ ] **M4: 프론트엔드 비교 뷰** — 2개 시나리오 선택 → ComparisonView 표시. 나란히 비교 (타임라인, 행위자, 지정학). diff 하이라이트 (증가=녹색, 감소=빨강).
  - 검증: 2개 시나리오 선택 → 비교 뷰에서 차이점 확인

- [ ] **M5: 대시보드** — AnalystDashboard 페이지. 시나리오 통계 (상태별, 지역별). 최근 활동 피드. 실행 중 시뮬레이션 진행률.
  - 검증: 대시보드에서 전체 시나리오 현황 한눈에 확인

## 5. 성공 기준

- 시나리오를 이름, 지역, 상태, 날짜로 검색/필터할 수 있다
- 2개 시뮬레이션 결과를 나란히 비교할 수 있다
- 대시보드에서 전체 시나리오 현황을 한눈에 확인할 수 있다

## 6. 위험 및 완화

| 위험 | 완화 |
|------|------|
| 비교 시 대용량 결과 데이터 로드 | 요약 통계만 비교. 상세 데이터는 on-demand 로드 |
| 검색 성능 (ILIKE) | 인덱스 추가 (name, region_name). 100개 이하에서는 충분 |

## 진행 로그

| 날짜 | 상태 | 내용 |
|------|------|------|
| 2026-03-21 | Draft | V4-5 분석관 워크스페이스 PRD 초안 작성 |
