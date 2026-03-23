# PRD: What-If Counterfactual Replay

> Status: Complete
> Created: 2026-03-23
> Dependencies: v4-interactive-simulation (M1,M2,M4,M5 완료)
> 관련 스펙: v4-interactive-simulation M3 재설계
> 버전: v7.0

---

## 1. 문제 정의

V4 인터랙티브 시뮬레이션에서 M3(What-If 분기)가 미완으로 남아 있다. 원래 설계는 MiroFish의 ManualAction 주입으로 라운드 N에서 상태를 포크하는 방식이었으나, **MiroFish API가 mid-simulation injection을 지원하지 않아** 구현이 불가능했다.

### 현황

| 역량 | 현재 상태 | 필요 |
|------|----------|------|
| 시뮬레이션 일시정지/재개 | ✅ M1 완료 | — |
| 이벤트 주입 (DB 저장) | ✅ M2 완료 (DB 저장만, MiroFish 미전달) | — |
| ManualAction → MiroFish IPC | ❌ API 미지원 | ❌ MiroFish 업스트림 의존 |
| 라운드 N 상태 포크 | ❌ 불가 | ❌ MiroFish checkpoint restore 미지원 |
| 대안 시나리오 비교 | ScenarioComparator 존재 (기본) | ❌ 정량적 메트릭 부족 |
| AI 개입 제안 | ✅ M5 TensionAnalyzer 완료 | — |

### 제약 조건

MiroFish 클라이언트 API 분석 결과:
- `generate_ontology(seed_text)` → 가설이 모델에 도달하는 **유일한 경로**
- `project_id`/`graph_id` 재사용 시 가설 미반영 → "같은 세계, 다른 랜덤성"
- `start_simulation()` 파라미터(`max_rounds`, `platform`)만 변경 가능
- 시뮬레이션 중간 상태 복원/포크 불가

## 2. 솔루션 개요

**Counterfactual Replay**: "라운드 N에서 포크" 대신 **"수정된 전제에서 전체 재실행"** 패러다임.

```
분석관: 시뮬레이션 중 라운드 5에서 일시정지
        "중국 함대가 철수했다면?" 가설 입력
             ↓
시스템:  augmented_seed = original_seed + "\n\nWhat-If 가설: {modification}"
        generate_ontology(augmented_seed)   → new project_id
        build_graph(project_id)             → new graph_id
        create_simulation(project_id)       → new simulation_id
        prepare_simulation(simulation_id)   → profiles
        start_simulation(simulation_id, max_rounds=원본과_동일)
             ↓
비교:    원본 전체 타임라인 vs 분기 전체 타임라인
         MAXS-inspired 메트릭으로 정량 비교
```

### 핵심 설계 결정

| 결정 | 선택 | 근거 |
|------|------|------|
| 파이프라인 전략 | Full regeneration (ontology → graph → sim) | seed_text가 유일한 가설 입력 경로 |
| 실행 길이 | 원본과 동일한 max_rounds | 대칭 비교. remaining_rounds는 개입 효과와 horizon 절단을 혼재 |
| branch_point_round | 메타데이터 전용 | 분석관 컨텍스트. 시뮬레이터 상태가 아님 |
| 비교 메트릭 | Heuristic ranking proxy | MAXS 등가물이 아닌 사후 분석 |
| 동시 실행 | 시나리오당 직렬 | MiroFish project-level race condition 방지 |

### 향후 확장 트리거

- MiroFish가 checkpoint restore 또는 mid-run event injection 지원 시 → true fork 모델로 전환
- 단일 실행 비교가 확률적 변동과 구분 불가능한 경우 → repeat runs (동일 시드 N회)

## 3. 기술 상세

### 3.1 DB 스키마

```sql
CREATE TABLE IF NOT EXISTS whatif_branches (
    id TEXT PRIMARY KEY,
    scenario_id TEXT NOT NULL REFERENCES scenarios(id),
    parent_result_id TEXT NOT NULL,          -- 원본 시뮬레이션 결과 ID
    branch_result_id TEXT,                   -- 분기 시뮬레이션 결과 ID (실행 시작 시 생성)
    branch_point_round INTEGER,              -- 메타데이터: 분석관이 가설을 입력한 라운드
    modification TEXT NOT NULL,              -- 사용자 가설 텍스트
    execution_mode TEXT DEFAULT 'full_replay',         -- full_replay | parameter_variant
    world_model_strategy TEXT DEFAULT 'regenerate',    -- regenerate | reuse
    status TEXT DEFAULT 'pending',           -- pending | running | completed | failed
    comparison_data TEXT,                    -- JSON: MAXS-inspired 비교 메트릭
    created_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_whatif_branches_scenario ON whatif_branches(scenario_id);
CREATE INDEX IF NOT EXISTS idx_whatif_branches_status ON whatif_branches(status);
```

### 3.2 Pydantic 모델

```python
class WhatIfCreateRequest(BaseModel):
    modification: str                           # 가설 ("중국 함대가 철수했다면?")
    branch_point_round: int | None = None       # 메타데이터 (선택)
    execution_mode: str = "full_replay"         # full_replay | parameter_variant
    max_rounds_override: int | None = None      # None이면 원본과 동일

class WhatIfBranch(BaseModel):
    id: str
    scenario_id: str
    parent_result_id: str
    branch_result_id: str | None
    branch_point_round: int | None
    modification: str
    execution_mode: str
    world_model_strategy: str
    status: str
    comparison_data: dict | None
    created_at: str
    completed_at: str | None

class WhatIfComparison(BaseModel):
    branch_id: str
    tension_advantage: float                    # branch_final - original_final
    tension_curves: dict                        # {"original": [...], "branch": [...]}
    step_variance: dict                         # {"original": float, "branch": float}
    slope_variance: dict                        # {"original": float, "branch": float}
    actor_diff: dict                            # {only_original, only_branch, common}
    action_count_delta: int                     # branch_count - original_count
    geopolitics_delta: int                      # branch_geo - original_geo
```

### 3.3 API 엔드포인트

```
POST /api/scenario/{id}/simulation/whatif
  Request:  WhatIfCreateRequest
  Response: WhatIfBranch (status="running")
  동작:     augmented_seed 생성 → 새 simulation_results 레코드 → BackgroundTask로 파이프라인 실행

GET /api/scenario/{id}/simulation/whatif
  Response: list[WhatIfBranch]
  동작:     시나리오의 전체 분기 목록 반환

GET /api/scenario/{id}/simulation/whatif/{branch_id}
  Response: WhatIfBranch
  동작:     단일 분기 상태 조회

GET /api/scenario/{id}/simulation/whatif/{branch_id}/compare
  Response: WhatIfComparison
  동작:     원본/분기 비교 메트릭 계산 및 반환
```

### 3.4 WhatIfEngine 서비스

```python
class WhatIfEngine:
    def __init__(self, mf_client, sb_client=None):
        self.orchestrator = SimulationOrchestrator(mf_client, sb_client)

    async def create_branch(self, scenario_id, parent_result_id, request) -> str:
        """분기 레코드 생성 + 파이프라인 시작."""
        # 1. 원본 시드 조회
        # 2. augmented_seed = original_seed + "\n\nWhat-If 가설: " + modification
        # 3. whatif_branches 레코드 INSERT
        # 4. simulation_results 레코드 INSERT (branch용)
        # 5. orchestrator.run_pipeline() BackgroundTask 등록
        # 6. branch_id 반환

    async def compare(self, branch_id) -> dict:
        """원본과 분기의 MAXS-inspired 비교 메트릭 계산."""
        # 1. parent/branch simulation_results 조회
        # 2. 양쪽 actions에서 per-round tension 계산
        # 3. tension_advantage = branch_final - original_final
        # 4. step_variance = variance(per_round_tensions)
        # 5. slope_variance = variance(round_to_round_diffs)
        # 6. actor/action/geopolitics diff 계산
        # 7. comparison_data JSON으로 whatif_branches UPDATE
        # 8. WhatIfComparison 반환
```

### 3.5 MAXS-Inspired 비교 메트릭

[MAXS 논문](https://arxiv.org/html/2601.09259v1) (Zhang et al., 2025)의 Value Estimation 프레임워크에서 3가지 개념을 시뮬레이션 비교에 차용:

| MAXS 원본 | 차용 적용 | 산출 방식 |
|-----------|----------|----------|
| Advantage Score (A_i) | Tension Advantage | `branch_final_tension - original_final_tension` |
| Step-Level Variance (V_step) | Step Variance | `var([tension_round_1, ..., tension_round_N])` — 궤적 안정성 |
| Slope-Level Variance (V_slope) | Slope Variance | `var([Δt_1, Δt_2, ..., Δt_{N-1}])` — 추세 일관성 |

```python
def compute_maxs_metrics(original_actions: list, branch_actions: list, max_rounds: int) -> dict:
    """MAXS-inspired heuristic comparison metrics."""
    orig_tensions = [compute_round_tension(original_actions, r) for r in range(1, max_rounds + 1)]
    branch_tensions = [compute_round_tension(branch_actions, r) for r in range(1, max_rounds + 1)]

    def _variance(values):
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        return sum((v - mean) ** 2 for v in values) / len(values)

    def _slope_variance(values):
        diffs = [values[i+1] - values[i] for i in range(len(values) - 1)]
        return _variance(diffs) if diffs else 0.0

    return {
        "tension_advantage": (branch_tensions[-1] if branch_tensions else 0)
                           - (orig_tensions[-1] if orig_tensions else 0),
        "tension_curves": {"original": orig_tensions, "branch": branch_tensions},
        "step_variance": {
            "original": _variance(orig_tensions),
            "branch": _variance(branch_tensions),
        },
        "slope_variance": {
            "original": _slope_variance(orig_tensions),
            "branch": _slope_variance(branch_tensions),
        },
    }
```

**해석 가이드**:
- `tension_advantage < 0` → 분기가 긴장 완화 효과 (가설이 긴장을 낮춤)
- `step_variance` 낮음 → 궤적이 안정적 (급변 없음)
- `slope_variance` 낮음 → 추세가 일관적 (예측 가능한 진행)
- ⚠️ 단일 실행 비교이므로 확률적 변동 포함 — "heuristic" 라벨 명시

### 3.6 프론트엔드

#### 레이아웃 제약

현재 페이지 구조:
- 전체 뷰포트: 100vw × 100vh 지도 (MaplibreViewer)
- 왼쪽 패널: OSINT — 400px 고정
- 오른쪽 패널: Simulation — **400px 고정** ← 비교 차트/메트릭에 부족

#### UI 전략: 2-Zone 분리

비교 분석은 정보 밀도가 높아 400px 사이드 패널에 수용 불가.
**분기 생성**은 기존 패널에, **비교 뷰**는 오버레이 모달로 분리한다.

| Zone | 위치 | 컴포넌트 | 내용 |
|------|------|---------|------|
| **A. 패널 내 탭** | SimulationPanel 400px | `WhatIfBranchView.tsx` | 분기 생성 폼 + 분기 목록 (가벼움) |
| **B. 오버레이 모달** | 지도 위 중앙, z-index: 30 | `WhatIfCompareModal.tsx` | 비교 차트 + MAXS 메트릭 + 행위자 diff (넓은 공간) |

#### Zone A: 패널 내 분기 관리 (400px)

```
┌─ SimulationPanel (400px) ─────────────┐
│ [...다른 탭들] [What-If]               │
│                                        │
│ ┌─ 새 분기 생성 ─────────────────────┐ │
│ │ 가설:                               │ │
│ │ [중국 함대가 철수했다면?       ]    │ │
│ │                      [분기 실행]   │ │
│ └─────────────────────────────────────┘ │
│                                        │
│ ┌─ 분기 목록 ────────────────────────┐ │
│ │                                     │ │
│ │ #1 "중국 함대 철수"                  │ │
│ │    ✅ 완료  R5에서 생성              │ │
│ │    긴장도 Δ: -0.23     [비교 보기]  │ │
│ │                                     │ │
│ │ #2 "항행의 자유 작전 강화"           │ │
│ │    🔄 실행중 (3/10)                 │ │
│ │                                     │ │
│ └─────────────────────────────────────┘ │
└────────────────────────────────────────┘
```

#### Zone B: 오버레이 비교 모달 (80vw × 85vh)

분기 목록에서 **[비교 보기]** 클릭 시 열림. 지도 위에 반투명 백드롭 + 중앙 모달.

```
┌── 백드롭 (rgba(0,0,0,0.6), z-index: 29) ──────────────────────────────────────────┐
│                                                                                     │
│  ┌── WhatIfCompareModal (80vw × 85vh, z-index: 30) ─────────────────────────────┐  │
│  │ ┌─ 헤더 ──────────────────────────────────────────────────────────────────┐   │  │
│  │ │ What-If 비교: "중국 함대 철수"                                    [✕]  │   │  │
│  │ │ 원본 시나리오: 남중국해 긴장 고조  ·  분기 시점: 라운드 5              │   │  │
│  │ └────────────────────────────────────────────────────────────────────────┘   │  │
│  │                                                                              │  │
│  │ ┌─ 긴장도 곡선 비교 (Recharts, 전체 너비) ─────────────────────────────┐   │  │
│  │ │                                                                      │   │  │
│  │ │  0.8 ─┐              ╱──── 원본 (실선)                              │   │  │
│  │ │  0.6  │         ╱──╱                                                │   │  │
│  │ │  0.4  │    ╱──╱        ╲──── 분기 (점선)                           │   │  │
│  │ │  0.2  │ ──╱                                                         │   │  │
│  │ │  0.0 ─┴───────────────────────────────────────────                   │   │  │
│  │ │       R1   R2   R3   R4   R5   R6   R7   R8   R9   R10             │   │  │
│  │ │                                                                      │   │  │
│  │ └──────────────────────────────────────────────────────────────────────┘   │  │
│  │                                                                              │  │
│  │ ┌─ MAXS 메트릭 (3-column grid) ───────────────────────────────────────┐   │  │
│  │ │ ┌─────────────────┐ ┌──────────────────┐ ┌──────────────────┐      │   │  │
│  │ │ │  Advantage       │ │  Step Variance    │ │  Slope Variance  │      │   │  │
│  │ │ │  -0.23           │ │  원본: 0.04       │ │  원본: 0.03      │      │   │  │
│  │ │ │  분기가 긴장 완화 │ │  분기: 0.02       │ │  분기: 0.01      │      │   │  │
│  │ │ │  ▼ 개선          │ │  ▼ 더 안정적      │ │  ▼ 더 일관적     │      │   │  │
│  │ │ └─────────────────┘ └──────────────────┘ └──────────────────┘      │   │  │
│  │ └──────────────────────────────────────────────────────────────────────┘   │  │
│  │                                                                              │  │
│  │ ┌─ 행위자 비교 (2-column) ────────────────────────────────────────────┐   │  │
│  │ │  원본만 출현             │  분기만 출현                              │   │  │
│  │ │  · 일본 해상자위대        │  · 중국 외교부 대변인                     │   │  │
│  │ │  · 필리핀 해안경비대      │  · ASEAN 사무국                          │   │  │
│  │ │──────────────────────────┼───────────────────────────────────────── │   │  │
│  │ │  공통 행위자: 8명         │  액션 수 차이: +12건                     │   │  │
│  │ └──────────────────────────────────────────────────────────────────────┘   │  │
│  │                                                                              │  │
│  │  ⚠️ Heuristic 분석 — 단일 실행 기반 추정치. 확률적 변동을 포함합니다.       │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

#### gatewayApi.ts 추가 함수

```typescript
export function createWhatIfBranch(scenarioId: string, data: {
  modification: string;
  branch_point_round?: number;
}): Promise<WhatIfBranch>

export function getWhatIfBranches(scenarioId: string): Promise<WhatIfBranch[]>

export function getWhatIfBranch(scenarioId: string, branchId: string): Promise<WhatIfBranch>

export function getWhatIfComparison(scenarioId: string, branchId: string): Promise<WhatIfComparison>
```

#### SimulationPanel.tsx 통합
- Tab type에 `"what_if"` 추가
- 시뮬레이션 실행 중/완료 상태에서 탭 표시
- `WhatIfBranchView` 컴포넌트 렌더링 (Zone A)

#### 오버레이 모달 동작
- `WhatIfBranchView`의 [비교 보기] 클릭 → `WhatIfCompareModal` 오픈 (Zone B)
- 모달은 `page.tsx` 레벨에서 포탈 렌더링 (z-index: 30, 패널 위)
- ESC 키 또는 백드롭 클릭으로 닫기
- 닫아도 패널의 분기 목록은 유지

### 3.7 수정 대상 파일

```
# 신규
backend/app/services/whatif_engine.py                           # WhatIfEngine 서비스
frontend/src/components/simulation/WhatIfBranchView.tsx         # Zone A: 패널 내 분기 관리
frontend/src/components/simulation/WhatIfCompareModal.tsx       # Zone B: 오버레이 비교 모달

# 수정
backend/app/database.py                          # whatif_branches 테이블 추가
backend/app/models/interactive.py                # WhatIfCreateRequest, WhatIfBranch, WhatIfComparison 모델
backend/app/routers/simulation.py                # 4개 엔드포인트 추가
frontend/src/lib/gatewayApi.ts                   # 4개 API 함수 추가
frontend/src/components/simulation/SimulationPanel.tsx  # What-If 탭 추가
frontend/src/app/page.tsx                        # 모달 상태 관리 + WhatIfCompareModal 포탈 렌더링
```

## 4. 마일스톤

- [x] **M1: DB 스키마 + 모델** — `whatif_branches` 테이블. `WhatIfCreateRequest`, `WhatIfBranch`, `WhatIfComparison` Pydantic 모델.
  - 검증: 서버 시작 시 테이블 자동 생성 확인

- [x] **M2: WhatIfEngine 서비스** — `create_branch()`: augmented_seed 생성 → full pipeline 실행. `compare()`: MAXS-inspired 메트릭 계산.
  - 검증: 기존 시나리오에서 분기 생성 → 파이프라인 완료 → comparison_data JSON 생성

- [x] **M3: API 엔드포인트** — 4개 엔드포인트 (create, list, get, compare). BackgroundTask로 파이프라인 비동기 실행.
  - 검증: curl로 분기 생성 → 상태 폴링 → 완료 후 비교 API 호출

- [x] **M4: 프론트엔드 2-Zone UI** — Zone A: `WhatIfBranchView` (400px 패널 내 분기 생성 폼 + 목록 + 상태 폴링). Zone B: `WhatIfCompareModal` (80vw×85vh 오버레이 — 긴장도 곡선 Recharts 차트, MAXS 3-column 메트릭 카드, 행위자 2-column diff). `page.tsx`에서 모달 상태 관리 + 포탈 렌더링.
  - 검증: 패널에서 가설 입력 → 분기 생성 → [비교 보기] 클릭 → 오버레이 모달에서 차트/메트릭 확인 → ESC로 닫기

- [x] **M5: v4-interactive-simulation M3 완료 처리** — 기존 PRD의 M3 체크박스를 완료로 변경. 진행 로그에 설계 변경 사유 기록.
  - 검증: v4-interactive-simulation.md Status: Complete

## 5. 성공 기준

- 완료된 시뮬레이션 또는 일시정지된 시뮬레이션에서 가설을 입력하여 What-If 분기를 생성할 수 있다
- 분기 시뮬레이션이 full pipeline으로 자동 실행된다
- 원본과 분기의 MAXS-inspired 비교 메트릭 (tension_advantage, step_variance, slope_variance)이 계산된다
- 프론트엔드 오버레이 모달(80vw×85vh)에서 긴장도 곡선 비교 차트와 행위자 차이를 확인할 수 있다
- v4-interactive-simulation PRD가 100% 완료 상태가 된다

## 6. 위험 및 완화

| 위험 | 완화 |
|------|------|
| Full pipeline 재실행으로 시간/비용 증가 | 동시 분기 최대 3개 제한. 파이프라인 완료까지 분석관에게 진행률 표시 |
| 단일 실행 비교의 확률적 변동 | 비교 결과에 "heuristic 추정치" 라벨 명시. 향후 repeat runs 확장 |
| 동시 MiroFish 요청 충돌 | 시나리오당 분기 직렬 실행 (큐잉) |
| augmented_seed가 온톨로지 품질 저하 유발 | 가설을 별도 섹션으로 명확히 구분. 원본 시드 훼손 방지 |
| MiroFish 업스트림 변경 시 설계 전환 필요 | execution_mode/world_model_strategy 필드로 미래 전략 대비 |

## 7. 참고 문헌

- **MAXS 논문**: Zhang et al., "MAXS: Meta-Adaptive Exploration with LLM Agents", arXiv:2601.09259v1, 2025.
  - Advantage Score, Step-Level Variance, Slope-Level Variance 개념 차용
  - 원논문은 LLM 추론 시 토큰 레벨 value estimation; 본 구현은 시뮬레이션 레벨 heuristic proxy로 재해석

## 진행 로그

| 날짜 | 상태 | 내용 |
|------|------|------|
| 2026-03-23 | Draft | v4 M3 재설계 PRD 작성. MiroFish ManualAction 미지원 확인 → counterfactual replay 패러다임으로 전환. MAXS 논문 메트릭 차용 설계. Oracle 아키텍처 검증 완료. |
| 2026-03-23 | Draft | UI 설계 변경: 400px 사이드 패널에 비교 뷰 수용 불가 → 2-Zone 분리 (패널: 분기 관리, 오버레이 모달: 비교 분석). 수정 대상 파일 8개 → 9개 (WhatIfCompareModal.tsx + page.tsx 추가). |
| 2026-03-23 | Complete | M1~M5 전체 구현 완료. BE: database.py, models/interactive.py, services/whatif_engine.py, routers/simulation.py. FE: gatewayApi.ts, WhatIfBranchView.tsx, WhatIfCompareModal.tsx, SimulationPanel.tsx, page.tsx. TS 타입체크 통과. v4 PRD Status: Complete 변경. |
