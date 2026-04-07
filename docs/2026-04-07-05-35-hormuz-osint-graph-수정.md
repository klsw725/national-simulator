# Hormuz OSINT/graph 수정

- 시간: 2026-04-07 05:35 UTC
- 사용자 프롬프트: `호르무즈 해협 관련 시뮬레이션 요청이였는데 관련 내용은 빠져 있고 osint 데이터도 안 들어간거 같다...?` / `그래프 데이터도 없는거 같다?`

## 원인

- 시뮬레이션 시작 시 생성된 seed 문서 대신 질문(question)만 `seed_text`로 전달하고 있었다.
- simulation-service의 상황 요약 프롬프트가 지역명/질문 제약 없이 희소한 OSINT를 그대로 LLM에 넘겨 일반론적 지역 정세를 생성할 수 있었다.
- actor 생성 노드가 actor 추출 실패 시 `US/CN/KR`로 고정 fallback 되어 Hormuz 요청에도 동북아 행위자가 선택될 수 있었다.
- 백엔드에 `/api/scenario/{scenario_id}/live/graph_data` 라우트가 없어 프론트 그래프 탭이 빈 상태가 될 수 있었다.

## 수정 사항

- simulation start payload에 `region_name`, `question`을 포함하고, seed가 있으면 seed 본문을 우선 사용하도록 수정.
- 상황 요약 프롬프트에 지역/질문/희소 데이터 제약을 추가.
- `create_actors_node`가 추출 엔티티와 지역명 기반으로 행위자를 고르도록 수정하고 Hormuz 기본 행위자 세트를 추가.
- 최신 LangGraph checkpoint의 `extracted_entities` / `extracted_relations`를 GraphTab이 읽을 수 있도록 `live/graph_data` API를 추가.

## 검증

- `frontend`: `npm run build` 통과
- `simulation-service`: `uv run python -m py_compile ...` 통과
- `backend`: `uv run python -m py_compile app/routers/simulation_v2.py app/routers/simulation_data.py` 통과
