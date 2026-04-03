# 작업 요약: prepare timeout 상향

## 사용자 프롬프트

```text
파봐
```

## 원인

- Gateway는 MiroFish prepare 단계를 최대 900초까지만 기다렸다.
- 그러나 실제 재현 시나리오 `scn_49bb421de613` / `sim_dd813162bb5b`는 prepare가 900초를 초과해 진행되었고,
  Gateway는 `TimeoutError: Task timed out after 900.0s`로 실패 처리했다.
- 이후 MiroFish 내부 상태를 확인해보면 같은 시뮬레이션은 실제로 `status=ready`, `config_generated=true`, `profiles_count=27` 상태로 완료되어 있었다.

## 변경 사항

- `backend/app/config.py`
  - `prepare_timeout` 기본값을 `900.0` → `1800.0`으로 상향
- `.env.example`
  - `PREPARE_TIMEOUT=1800`으로 갱신
- `.env`
  - 현재 개발 환경에서도 즉시 반영되도록 `PREPARE_TIMEOUT=1800`으로 갱신

## 의도

- prepare 단계의 실제 소요 시간이 긴 시나리오에서도 false failure를 줄인다.
- MiroFish가 늦게라도 정상적으로 `ready`에 도달하는 경우 Gateway가 중간에 실패로 오판하지 않도록 한다.

## 검증 포인트

- 기존 실패 로그: `TimeoutError: Task timed out after 900.0s`
- 같은 시뮬레이션의 MiroFish 최종 상태: `ready`, `config_generated=true`, `error=null`
