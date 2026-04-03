# geopolitics_mapper.py 중복 제거 버그 수정

## 사용자 프롬프트

> 시뮬레이션이 잘 적용된건가? 아닌거 같은데

지정학적 시뮬레이션 보고서가 "참여 엔티티 0명, 행동 데이터 전무"를 보고하여 원인 진단 요청.

## 문제

`backend/app/services/geopolitics_mapper.py`의 `map_actions_to_geopolitics()` 함수에서 중복 제거 셋(`seen_event_types_this_round`)이 **함수 전체에서 한 번만 초기화**되어 라운드 간 리셋되지 않았음.

`GEOPOLITICS_ACTION_MAP`의 고유 매핑 타입이 3종뿐(`diplomatic_statement`, `strategic_observation`, `treaty_sign`)이라, 전체 액션 중 최대 3~4개만 살아남고 나머지 97%가 소실됨.

### 재현 데이터

| 측정 지점 | 액션 수 |
|-----------|---------|
| MiroFish 원본 | 109개 (23 엔티티, 10 라운드) |
| 버그 있는 매핑 후 | **3개** (97.2% 손실) |
| Gateway DB 저장 | 3개 |
| 보고서 결론 | "참여 엔티티 0명" |

## 수정 내용

**파일**: `backend/app/services/geopolitics_mapper.py`

중복 제거 키를 `geo_type` (글로벌) → `(round_num, agent_id, geo_type)` (라운드+에이전트 단위)로 변경.

- 같은 에이전트가 같은 라운드에서 동일 유형 액션 반복 시에만 중복 제거
- 다른 에이전트의 액션, 다른 라운드의 액션은 모두 보존

### 수정 후 검증

| 측정 지점 | 액션 수 |
|-----------|---------|
| MiroFish 원본 | 109개 |
| 수정된 매핑 후 | **109개** (100% 보존) |
