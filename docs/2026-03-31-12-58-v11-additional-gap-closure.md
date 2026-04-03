# v11 추가 갭 보완

- 날짜: 2026-03-31 12:58 UTC
- 사용자 프롬프트: `2`

## 목적

이전 보완 이후에도 남아 있던 실질 갭을 추가로 줄였다. 이번에는 제약 적용 의미 보정, 단일 플랫폼 액션 메타데이터 보존, 실제 heartbeat 제어 경로, 라운드 번호 검증, mock/디브리프 동작 보강에 집중했다.

## 주요 변경

### Backend / External

- `backend/app/clients/mirofish.py`
  - round-control heartbeat API 클라이언트 추가
- `backend/app/services/simulation_orchestrator.py`
  - 실제 heartbeat control call 사용
  - round mismatch 검증 추가
  - auto-complete SSE에 round 포함
- `backend/app/services/context_injection.py`
  - system post를 Twitter/Reddit 양쪽으로 생성
  - `env_constraints`를 `create_post` 차단 의미로 정렬
- `external/mirofish-backend/app/api/simulation.py`
  - `/round_control/heartbeat` 추가
- `external/mirofish-backend/app/services/simulation_runner.py`
  - heartbeat 전달/ack 처리 추가
- `external/mirofish-backend/scripts/round_control_context.py`
  - 제약 판정 시 `blocked_actions`를 실제로 고려하도록 수정
- `external/mirofish-backend/scripts/run_parallel_simulation.py`
- `external/mirofish-backend/scripts/run_twitter_simulation.py`
- `external/mirofish-backend/scripts/run_reddit_simulation.py`
  - `create_post` 차단 기준으로 mute 적용
  - proceed round 번호 검증 추가
  - 단일 플랫폼 액션에 post metadata를 복구하여 source metadata 보존 강화

### Frontend

- `frontend/src/hooks/useWargame.ts`
  - mock mode에서 confirmation → simulation 자동 전환 추가
  - round snapshot 저장 및 조회 추가
  - completed hydration/polling 시 debrief 자동 연동
  - `decision_auto_completed` 이벤트 수신 추가
- `frontend/src/components/wargame/WarRoom.tsx`
  - selected round snapshot을 기준으로 PhaseBar/ContextPanel 표시
- `frontend/src/components/wargame/DecisionCard.tsx`
  - `predicted_deltas`, `state_deltas`, `delta_*`를 통합 렌더링
- `frontend/src/components/simulation/SimulationPanel.tsx`
  - 워게임 완료 후에도 기본적으로 War Room/디브리프 흐름 유지

## 검증

- Python 문법 검증
  - `python -m py_compile backend/app/services/context_injection.py backend/app/services/simulation_orchestrator.py backend/app/clients/mirofish.py external/mirofish-backend/app/services/simulation_runner.py external/mirofish-backend/app/api/simulation.py external/mirofish-backend/scripts/round_control_context.py external/mirofish-backend/scripts/run_parallel_simulation.py external/mirofish-backend/scripts/run_twitter_simulation.py external/mirofish-backend/scripts/run_reddit_simulation.py`
- Frontend build 검증
  - `npm run build` 성공

## 남은 여지

- 렌즈와 실제 지도 오버레이의 연결은 아직 제한적이다.
- 디브리프는 개선되었지만 완전한 과거 상태 복원형 AAR까지는 추가 구현 여지가 있다.
