# v11 워게임 루프 엔드투엔드 구현

- 날짜: 2026-03-31 12:18 UTC
- 사용자 프롬프트: `@docs/specs/v11-wargame-loop/spec.md 이거에 맞게 잘 구현되어 있는지 점검해봐 코드 단이 아니라 요청사항이 잘 되어 있는지를 확인해` → `구현해`

## 요약

v11 워게임 루프의 부분 구현 상태를 보완하기 위해 백엔드, 외부 MiroFish 라운드 제어, 프론트엔드 War Room 경로를 함께 수정했다.

## 주요 변경

### 백엔드

- `backend/app/services/simulation_orchestrator.py`
  - 워게임 SSE 페이로드 보강
  - 브리핑 생성/전달
  - heartbeat/TTL 상태 흐름 보정
  - recovery/decision_resolved payload 보강
- `backend/app/routers/simulation_run.py`
  - `/wargame_status` 응답에 role, actorId, briefing, decisionPoint 포함

### 외부 MiroFish

- `external/mirofish-backend/scripts/round_control_context.py` 신규
  - system post DB 주입
  - env constraint 병합/라운드 단위 제약 상태 관리
- `external/mirofish-backend/scripts/run_parallel_simulation.py`
  - 병렬 라운드 제어에서 inject_context 실제 반영
  - 제약 대상 agent DO_NOTHING 강제
- `external/mirofish-backend/scripts/run_twitter_simulation.py`
- `external/mirofish-backend/scripts/run_reddit_simulation.py`
  - 단일 플랫폼 ready 시점 수정
  - inject_context 실제 반영
  - 제약 대상 agent DO_NOTHING 강제
- `external/mirofish-backend/app/services/simulation_runner.py`
  - ready 검증 추가
  - round-control error 수신 시 실패 처리
- `external/mirofish-backend/app/api/simulation.py`
  - completed stop 시 상태를 completed로 반영

### 프론트엔드

- `frontend/src/lib/api/wargameApi.ts` 신규
- `frontend/src/lib/gatewayApi.ts`
- `frontend/src/hooks/useWargame.ts`
  - 초기 hydration 추가
  - SSE/폴링 상태 동기화 개선
  - decision_required fallback 강화
- `frontend/src/components/wargame/WarRoom.tsx`
  - 실제 decision resolve API 연결
  - Debrief/phase 흐름 보정
- `frontend/src/components/simulation/SimulationPanel.tsx`
  - 워게임 모드 live action 전달
- `frontend/src/components/wargame/FeedPanel.tsx`
  - 타임라인 스크럽 시 라운드 기반 필터링

## 검증

- Python 문법 검증:
  - `python -m py_compile`로 수정한 backend/external Python 파일 확인
- Frontend 빌드 검증:
  - `npm run build` 성공

## 남은 제약

- OASIS 내부 메모리/환경 구조상 system post 주입은 DB 주입 기반으로 구현했다.
- env constraint는 현재 hard mute 성격으로 `DO_NOTHING` 강제를 사용한다.
- 렌즈별 맵 오버레이 전환과 What-If 연계는 추가 백엔드/맵 연동 작업이 더 필요하다.
