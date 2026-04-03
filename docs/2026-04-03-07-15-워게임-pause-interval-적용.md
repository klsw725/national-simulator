# 작업 요약: 워게임 pause interval 적용

## 사용자 프롬프트

```text
1 (decision 생성 빈도 자체를 줄이는 로직)
```

## 배경

- 시뮬레이션이 끝까지 완주 가능해졌지만, round 2부터 매 라운드마다 geopolitics direction decision point가 생성되어 총 9번의 개입이 필요했다.
- `SimulationParams.geopolitics_rounds` (기본값 3)가 모델에 정의되어 있었지만 `should_pause`에서 사용되지 않고 있었다.

## 변경 사항

- `backend/app/services/geopolitics_interactive.py`
  - `should_pause()`에 `pause_interval` 파라미터 추가 (기본값 3)
  - cascade event가 아닌 일반 pause는 `(current_round - 2) % pause_interval == 0`인 라운드에서만 평가
  - 즉 `geopolitics_rounds=3`이면 round 2, 5, 8에서만 pause 가능 (cascade 제외)

- `backend/app/services/simulation_orchestrator.py`
  - `should_pause()` 호출 시 `pause_interval=simulation_params.geopolitics_rounds` 전달

## 기대 효과

- `geopolitics_rounds=3` 기준으로 10라운드 시뮬레이션에서 decision point가 최대 3~4번으로 줄어듦 (cascade 발생 시 추가 가능)
- 사용자가 `geopolitics_rounds` 값을 조절해서 개입 빈도를 직접 제어 가능

## 검증

- `python -m py_compile backend/app/services/geopolitics_interactive.py` 통과
- `python -m py_compile backend/app/services/simulation_orchestrator.py` 통과
