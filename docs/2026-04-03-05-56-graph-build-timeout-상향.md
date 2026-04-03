# 작업 요약: graph build timeout 상향

## 사용자 프롬프트

```text
계속 확인해
```

## 확인 결과

- prepare timeout을 1800초로 올린 뒤 새 시나리오 `scn_004a9356fc12`를 재검증했다.
- 그러나 이번에는 prepare까지 가지 못하고 Gateway 시나리오 상태가 `failed`가 되었다.
- MiroFish 그래프 태스크 `d3d20e9e-c0a2-4bac-83d0-0707c16c2d41`를 직접 확인하면 최종적으로:
  - `status=completed`
  - `graph_id=mirofish_e5d9399386aa4126`
  - `node_count=14`, `edge_count=71`
- 즉 실제 그래프 구축은 완료됐지만 Gateway가 먼저 실패로 간주한 false timeout 패턴이 graph build 단계에서도 재현됐다.

## 변경 사항

- `backend/app/config.py`
  - `graph_build_timeout` 기본값을 `900.0` → `1800.0`으로 상향
- `.env.example`
  - `GRAPH_BUILD_TIMEOUT=1800`으로 갱신
- `.env`
  - 현재 개발 환경에도 `GRAPH_BUILD_TIMEOUT=1800` 반영

## 의도

- 장시간 LLM/엔티티 추출이 걸리는 그래프 구축에서도 Gateway가 중간에 false failure를 내지 않도록 한다.
