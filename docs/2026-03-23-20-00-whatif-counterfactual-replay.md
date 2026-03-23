# What-If Counterfactual Replay 구현

> 날짜: 2026-03-23
> PRD: v7-whatif-counterfactual (v4-interactive-simulation M3 재설계)

## 프롬프트

```
1. PRD Next 실행 → v4-interactive-simulation M3 (What-If 분기 엔진)이 유일한 미완 작업으로 식별
2. MAXS 논문(arXiv:2601.09259v1) 적용 가능성 분석 → 직접 적용 불가, 개념적 차용 3가지 포인트 도출
3. MiroFish API 제약 분석 → ManualAction mid-simulation injection 미지원 확인
4. Oracle 아키텍처 검증 → "counterfactual replay" 패러다임으로 전환 결정
5. PRD 생성 → v7-whatif-counterfactual.md
6. UI 피드백 → 400px 패널 비교 뷰 부족 → 2-Zone (패널 + 오버레이 모달) 설계
7. M1~M5 순차 구현
```

## 변경 파일

### 신규 (3개)
- `backend/app/services/whatif_engine.py` — WhatIfEngine 서비스 (create_branch, run_branch_pipeline, compare, compute_maxs_metrics)
- `frontend/src/components/simulation/WhatIfBranchView.tsx` — Zone A: 400px 패널 내 분기 생성 폼 + 목록
- `frontend/src/components/simulation/WhatIfCompareModal.tsx` — Zone B: 80vw×85vh 오버레이 (Recharts 차트 + MAXS 메트릭 + 행위자 diff)

### 수정 (6개)
- `backend/app/database.py` — whatif_branches 테이블 + 인덱스 2개
- `backend/app/models/interactive.py` — WhatIfCreateRequest, WhatIfBranch, WhatIfComparison 모델
- `backend/app/routers/simulation.py` — 4개 엔드포인트 (POST create, GET list, GET detail, GET compare)
- `frontend/src/lib/gatewayApi.ts` — WhatIfBranch/WhatIfComparison 타입 + 4개 API 함수
- `frontend/src/components/simulation/SimulationPanel.tsx` — What-If 탭 + WhatIfBranchView 렌더링
- `frontend/src/app/page.tsx` — 모달 상태 관리 + WhatIfCompareModal 포탈 렌더링

### PRD (2개)
- `docs/prds/v7-whatif-counterfactual.md` — 신규 PRD 작성 → Status: Complete
- `docs/prds/v4-interactive-simulation.md` — M3 완료 + Status: Complete

## 핵심 설계 결정

| 결정 | 선택 | 근거 |
|------|------|------|
| 파이프라인 전략 | Full regeneration (ontology → graph → sim) | seed_text가 유일한 가설 입력 경로 |
| 실행 길이 | 원본과 동일한 max_rounds | 대칭 비교 |
| 비교 메트릭 | MAXS-inspired heuristic proxy | 논문의 Advantage/Step Var/Slope Var 개념 차용 |
| UI 배치 | 2-Zone (패널 + 오버레이 모달) | 400px 패널에 비교 차트 수용 불가 |
| 동시 실행 | 시나리오당 최대 3개 분기 | MiroFish race condition 방지 |

## 검증 결과

- Python 모델 import: OK
- MAXS 메트릭 계산: tension_advantage, step_variance, slope_variance 정상 동작
- API 엔드포인트 등록: 4개 확인
- TypeScript 타입체크: `npx tsc --noEmit` 에러 0건
