# v11 남은 갭 보완 구현

- 날짜: 2026-03-31 12:43 UTC
- 사용자 프롬프트: `2번 그리고 하면서 너가 테스트하면서 계속 검증해`

## 작업 목적

이전 재감사에서 남아 있던 v11 워게임 루프 잔여 갭을 추가로 보완했다. 특히 TTL 자동 진행, 이전 결정 결과 브리핑 반영, 시스템 포스트 다중 플랫폼 주입, 프론트엔드 디브리프 지속성, 선택지 예측 결과 렌더링을 중심으로 수정했다.

## 주요 변경

### Backend / External

- `backend/app/services/simulation_orchestrator.py`
  - TTL 만료 시 최신 pending decision을 자동 확정하고 워게임 루프를 이어가도록 보완
  - `previous_decision_outcome`을 다음 브리핑에 전달
- `backend/app/services/context_injection.py`
  - 시스템 포스트를 Twitter/Reddit 양쪽 플랫폼으로 생성
  - 사용자 결정/고강도 이벤트 기반 `env_constraints` 생성 유지

### Frontend

- `frontend/src/hooks/useWargame.ts`
  - `simulation_complete`에서 `final_state.tension` 형태를 올바르게 반영
  - hydration/polling 시 completed 상태면 디브리프를 자동 열 수 있도록 보정
- `frontend/src/components/wargame/DecisionCard.tsx`
  - `predicted_deltas`, `state_deltas`, `delta_*`를 함께 해석하여 선택지 예측 결과 렌더링 강화
- `frontend/src/components/simulation/SimulationPanel.tsx`
  - 완료된 워게임 시나리오도 기본적으로 War Room/디브리프 흐름을 유지하도록 조정 (`report` 탭 예외)

## 검증

- Python 문법 검증
  - `python -m py_compile backend/app/services/context_injection.py backend/app/services/simulation_orchestrator.py external/mirofish-backend/scripts/round_control_context.py external/mirofish-backend/scripts/run_parallel_simulation.py external/mirofish-backend/scripts/run_twitter_simulation.py external/mirofish-backend/scripts/run_reddit_simulation.py external/mirofish-backend/app/services/simulation_runner.py external/mirofish-backend/app/api/simulation.py`
- Frontend build 검증
  - `npm run build` 성공

## 비고

- 실제 MF heartbeat ACK 왕복은 현재 HTTP round-control 구조 제약상 run-status polling 보정이 섞여 있다.
- 디브리프/타임라인은 이전보다 나아졌지만 완전한 과거 상태 복원형 AAR까지는 추가 작업 여지가 있다.
