# 워게임 라운드 진행 오버레이 소실 버그 수정

## 사용자 프롬프트

> 야 그리고 분명히 라운드 진행중인데 왜 프론트 라운드 진행중입니다는 사라지는거야?

## 문제

워게임에서 사용자가 결정(escalate/diplomatic 등)을 선택하고 라운드가 재개되면, 백엔드가 `phase_change: "simulation"` SSE를 보냄. 프론트엔드가 이를 수신하면 phase가 `"simulation"`으로 바뀌어, `RoundProgressOverlay`(`phase === "confirmation"` 조건)가 사라짐.

### 타임라인

1. 사용자 결정 선택 → phase = `"confirmation"` (프론트) → `RoundProgressOverlay` 표시 중
2. 백엔드: `decision_resolved` SSE → phase 유지 ✅
3. 백엔드: `phase_change: "simulation"` SSE → phase = `"simulation"` ❌ 오버레이 소실
4. 백엔드: `round_complete` SSE 다수 → phase 변경 없음 → 빈 화면 지속

## 수정 내용

**파일**: `frontend/src/hooks/useWargame.ts`

`phase_change` SSE 핸들러에서, 결정 흐름 중(`briefing`/`decision`/`confirmation`)에 `"simulation"` phase가 오면 `"confirmation"`으로 매핑하여 라운드 진행 오버레이를 유지.

- 초기 시뮬레이션 시작 시 `phase_change: "simulation"`은 기존 phase가 `"simulation"`(초기 상태)이므로 영향 없음
- 다음 `phase_change: "briefing"` 수신 시 정상적으로 브리핑 오버레이 전환
