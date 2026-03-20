# PRD 4: Simulation Orchestration 구현

> 날짜: 2026-03-20
> 프롬프트: `prd-next` → PRD 4 (simulation-orchestration) 선택 → 구현

## 변경 사항

### 신규 파일

| 파일 | 설명 |
|------|------|
| `backend/app/clients/mirofish.py` | MiroFish HTTP 클라이언트 — 6단계 파이프라인 API 메서드, multipart ontology 업로드, 비동기 폴링 유틸리티(`poll_until_done`), health check |
| `backend/app/services/simulation_orchestrator.py` | SimulationOrchestrator — 6단계 순차 파이프라인 실행, BackgroundTask에서 호출, 각 단계 완료 후 DB 상태 업데이트, 타임아웃 설정, 에러 시 failed 전이 |

### 수정 파일

| 파일 | 변경 내용 |
|------|-----------|
| `backend/app/routers/simulation.py` | PRD 4 스텁(501) 3개를 실제 구현으로 교체: `POST /simulate`(202 + BackgroundTasks), `GET /status`, `GET /results`. MiroFish health check, seed 존재 확인, 중복 실행 방지 포함 |
| `backend/app/main.py` | MiroFishClient를 `app.state.mf_client`에 등록, lifespan에 close 추가 |

## 파이프라인 설계

```
POST /api/scenario/{id}/simulate (202 Accepted)
  → BackgroundTask: SimulationOrchestrator.run_pipeline()
    → Step 1: ontology/generate (동기) → project_id
    → Step 2: graph/build (비동기 폴링) → graph_id
    → Step 3: simulation/create (동기) → simulation_id
    → Step 4: simulation/prepare (비동기 폴링) → profiles ready
    → Step 5: simulation/start (비동기 폴링) → completed
    → Step 6: report/generate (비동기 폴링) → report ready
    → 결과 수집 → DB 저장 → status=completed
```

## 상태 머신

```
시나리오: created → simulating → completed | failed
파이프라인: starting → simulating:ontology → simulating:graph_build
  → simulating:create → simulating:prepare → simulating:running
  → simulating:report → completed | failed
```

## 검증 결과

- ✅ 전체 import 검증 통과
- ✅ FastAPI 앱 기동 + 신규 라우트 등록 확인
- ✅ POST /simulate, GET /status, GET /results 라우트 활성화
- ✅ MiroFishClient가 app.state에 등록됨
