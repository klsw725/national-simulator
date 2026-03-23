# PRD: 인터랙티브 시뮬레이션

> Status: Partial
> Created: 2026-03-21
> Dependencies: v4-ai-guided-decisions, v3-simulation-params, v2-pipeline-checkpoints
> 관련 스펙: `specs/V4-SPEC.md` PRD V4-2
> 버전: v4.0

---

## 1. 문제 정의

시뮬레이션이 시작되면 완료까지 분석관이 개입할 수 없다. 라운드 중간에 이벤트를 주입하거나 에이전트 행동을 조정할 수 없으며, 대안 시나리오를 탐색하려면 처음부터 새 시뮬레이션을 실행해야 한다.

## 2. 솔루션 개요

- **라운드별 일시정지** — 지정된 라운드에서 자동 일시정지. AI가 상황 변화를 감지하면 개입을 제안.
- **이벤트 주입** — 분석관이 시뮬레이션 중간에 외부 이벤트를 주입 (뉴스 발표, 군사 행동 등)
- **What-If 분기** — 현재 라운드 상태를 스냅샷하여 대안 시나리오를 병렬 실행. 원본과 비교.
- **AI 개입 제안** — 긴장도 급등, 패턴 이상 감지 시 AI가 자동으로 분석관에게 알림.

## 3. 기술 상세

### 3.1 라운드별 일시정지

```python
class InteractiveSimulationConfig(BaseModel):
    pause_at_rounds: list[int] = []  # 지정 라운드에서 일시정지
    auto_pause_on_tension: bool = True  # 긴장도 급등 시 자동 일시정지
    tension_threshold: float = 0.7  # 자동 일시정지 긴장도 임계치
    max_pause_duration_minutes: int = 30  # 일시정지 최대 시간 (초과 시 자동 재개)
```

MiroFish simulation_runner의 IPC를 활용하여 라운드 간 일시정지/재개 명령 전달.

### 3.2 이벤트 주입

```
POST /api/scenario/{id}/simulation/inject_event
{
    "event_type": "news_announcement",
    "content": "UN 안보리가 남중국해 긴급 회의 소집",
    "target_agents": ["all"],  // 또는 특정 에이전트 목록
    "as_initial_post": true     // ManualAction으로 시뮬레이션에 주입
}
```

MiroFish IPC의 기존 명령 체계를 활용하여 ManualAction 주입.

### 3.3 What-If 분기

```python
class WhatIfBranch(BaseModel):
    id: str
    parent_result_id: str
    branch_point_round: int
    modification: str  # "중국 함대 철수", "미국 항행의 자유 작전 강화"
    status: str  # "running" | "completed" | "failed"
    
# 분기 프로세스:
# 1. 현재 라운드의 시뮬레이션 상태 스냅샷
# 2. 수정 사항을 ManualAction으로 적용
# 3. 새 시뮬레이션으로 나머지 라운드 실행
# 4. 원본 결과와 분기 결과 비교 API
```

### 3.4 AI 개입 제안

시뮬레이션 실행 중 라운드별 액션을 분석하여 이상 패턴 감지:
- 긴장도 급등 (연속 3라운드 상승)
- 특정 행위자의 극단적 행동 패턴
- 예상과 다른 동맹/적대 관계 변화

감지 시 DecisionPoint (V4-1) 생성 → 분석관에게 알림.

### 3.5 수정 대상 파일

```
# 신규
backend/app/models/interactive.py               # InteractiveSimulationConfig, WhatIfBranch
backend/app/services/tension_analyzer.py         # 긴장도 분석 + 이상 감지
frontend/src/components/simulation/InteractiveSimulationView.tsx  # 인터랙티브 UI

# 수정
backend/app/services/simulation_orchestrator.py  # interactive 모드 라운드별 일시정지
backend/app/routers/simulation.py                # inject_event, whatif, pause/resume API
backend/app/clients/mirofish.py                  # IPC 명령 전달 (pause, inject)
frontend/src/components/simulation/SimulationPanel.tsx  # 인터랙티브 탭
frontend/src/types/simulation.ts                 # InteractiveConfig, WhatIfBranch 타입
```

## 4. 마일스톤

- [x] **M1: 라운드별 일시정지 API** — InteractiveSimulationConfig 모델. pause_at_rounds 설정. MiroFish IPC로 pause/resume 명령 전달. 일시정지 시 현재 라운드 데이터 반환.
  - 검증: pause_at_rounds=[5]로 실행 → 라운드 5에서 일시정지 → resume 후 진행

- [x] **M2: 이벤트 주입 API** — POST /inject_event 엔드포인트. ManualAction으로 변환하여 MiroFish IPC 전달. 주입된 이벤트가 다음 라운드에 반영.
  - 검증: 일시정지 상태에서 이벤트 주입 → resume → 에이전트가 주입된 이벤트에 반응

- [ ] **M3: What-If 분기 엔진** — 현재 라운드 상태 스냅샷. 수정 사항 적용 후 별도 시뮬레이션 실행. 원본/분기 결과 비교 API.
  - 검증: 라운드 5에서 분기 → 분기 시뮬레이션 완료 → 원본과 비교 API 동작

- [x] **M4: 프론트엔드 InteractiveSimulationView** — 라운드별 타임라인 + 일시정지 인디케이터. 이벤트 주입 폼. What-If 분기 생성 UI. 원본/분기 비교 뷰.
  - 검증: 일시정지 시 UI에서 이벤트 주입/분기 생성 가능

- [x] **M5: AI 개입 제안 엔진** — 라운드별 긴장도 분석. 이상 패턴 감지 (긴장도 급등, 극단적 행동). 감지 시 DecisionPoint 생성 → 프론트엔드 알림.
  - 검증: 시뮬레이션 중 긴장도가 0.7 초과 시 AI가 "개입하시겠습니까?" 제안

## 5. 성공 기준

- 시뮬레이션 중 지정 라운드에서 일시정지 + 재개가 가능하다
- 일시정지 중 외부 이벤트를 주입하면 다음 라운드에 반영된다
- What-If 분기로 대안 시나리오를 병렬 실행하고 원본과 비교할 수 있다
- AI가 긴장도 급등 시 분석관에게 개입을 제안한다

## 6. 위험 및 완화

| 위험 | 완화 |
|------|------|
| What-If 분기로 LLM 비용 폭증 | 동시 분기 최대 3개. 분기당 최대 10라운드 |
| MiroFish IPC 타이밍 이슈 | pause 명령은 라운드 경계에서만 적용 (라운드 중간 불가) |
| 장시간 일시정지로 OASIS 상태 불안정 | 최대 30분 일시정지. 초과 시 자동 재개 |

## 진행 로그

| 날짜 | 상태 | 내용 |
|------|------|------|
| 2026-03-21 | Draft | V4-2 인터랙티브 시뮬레이션 PRD 초안 작성 |
| 2026-03-22 | Partial | M1,M2,M4,M5 구현. 일시정지/재개 + 이벤트 주입 + InteractiveSimulationView + TensionAnalyzer. M3(What-If) MiroFish 대기 |
