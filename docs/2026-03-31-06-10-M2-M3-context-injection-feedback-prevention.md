# M2 Context Injection Engine + M3 Feedback Runaway Prevention

## 사용자 프롬프트

```
1. TASK: Implement M2 (Context Injection Engine) + M3 (Feedback Runaway Prevention). These are tightly coupled — context injection creates tagged posts, feedback prevention filters them.

2. EXPECTED OUTCOME:
- New `backend/app/services/context_injection.py` with templates for 6 event types + user decisions
- Modified `backend/app/services/geopolitics_mapper.py` with source filtering + per-round debounce
- All system posts tagged with `metadata.source` for traceability
- geo_event and user_decision sourced actions excluded from geopolitics mapping

3. REQUIRED TOOLS: Read, Write, Edit, Grep, Glob, LSP tools

4. MUST DO:

**Step 0: Read existing code**
- Read `backend/app/services/geopolitics_mapper.py` — understand current `map_actions_to_geopolitics()` function
- Read `backend/app/geopolitics/events.py` — understand PROPAGATION_RULES, event types
- Read `backend/app/geopolitics/engine.py` — understand DecisionEngine, actor states
- Read `backend/app/services/geopolitics_interactive.py` — understand build_actor_response_options, build_direction_options
- Read `backend/app/models/scenario.py` — understand SimulationParams

**Step 1: Create `backend/app/services/context_injection.py`**

Implement the context injection engine as specified in the v11 spec (section 3.3):

- `EVENT_POST_TEMPLATES`: Dict mapping 6 event types (military_movement, military_exercise, sanction_impose, trade_restriction, diplomatic_statement, treaty_sign) to template dicts with `author` and `template` string.
- `DECISION_POST_TEMPLATES`: Dict mapping user decision actions to post templates. `do_nothing` maps to None (no post).
- `MAGNITUDE_DESCRIPTIONS`: Ranges mapping magnitude float ranges to Korean descriptions (소규모, 중규모, 대규모, 전례 없는 규모의).
- `build_inject_context(engine, round_result, user_decision=None) -> dict`: Main function that:
  1. Iterates over round_result events + cascade_events
  2. For each event, renders template with actor names, magnitude description
  3. Tags each system post with `metadata.source = "geo_event"`
  4. If user_decision provided, renders decision post template with `metadata.source = "user_decision"`
  5. Returns `{"system_posts": [...], "env_constraints": []}` structure

Helper functions:
- `_render_event_post(template, event, engine) -> str`: Fill template with actor names from engine, magnitude description
- `_get_magnitude_description(magnitude: float) -> str`: Map magnitude to Korean description

**Step 2: Modify `backend/app/services/geopolitics_mapper.py`**

Add source filtering and per-round debounce to `map_actions_to_geopolitics()`:

- Add `source_filter` parameter (optional)
- Skip actions where `metadata.source == "geo_event"` — these are agent reactions to system posts
- Skip actions where `metadata.source == "user_decision"` — already reflected in engine
- Add `seen_event_types_this_round` set for per-round debounce — same event type only mapped once per round
- Preserve ALL existing behavior when no metadata.source is present (backward compatible)

**Step 3: Verify**
- Run LSP diagnostics on both new/modified files
- Ensure no import errors
- Ensure existing geopolitics_mapper behavior is unchanged for actions without metadata

5. MUST NOT DO:
- Do NOT modify any MiroFish files (external/)
- Do NOT modify the geopolitics engine (engine.py, events.py)
- Do NOT modify frontend files
- Do NOT create commits
- Do NOT add new dependencies
- Do NOT implement actual OASIS injection (that's in the MiroFish stub from M1)
- Do NOT suppress type errors

6. CONTEXT:
- Working directory: /home/swlee/osint-simulator
- Backend uses Python 3.12, FastAPI, managed with uv
- Read the PRD: docs/specs/v11-wargame-loop/prds/v11-backend-wargame-engine.md (M2, M3 sections)
- The spec section 3.3 and 3.4 have the full implementation details
```

## 변경 요약

### 1) 신규 파일: `backend/app/services/context_injection.py`
- `EVENT_POST_TEMPLATES` 추가: 6개 지정학 이벤트 타입별 시스템 포스트 템플릿/작성자 정의
- `DECISION_POST_TEMPLATES` 추가: 사용자 결정 액션별 템플릿 정의 (`do_nothing`은 `None`)
- `MAGNITUDE_DESCRIPTIONS` 추가: 규모 범위별 한글 설명 매핑
- `_get_magnitude_description()` 추가: magnitude 범위에 따른 규모 설명 반환
- `_render_event_post()` 추가: 엔진 actor 이름 및 템플릿 변수 바인딩
- `build_inject_context()` 추가:
  - `events + cascade_events` 순회
  - 시스템 포스트 생성 시 `metadata.source = "geo_event"` 태깅
  - 사용자 결정 포스트 생성 시 `metadata.source = "user_decision"` 태깅
  - 반환 형태: `{"system_posts": [...], "env_constraints": []}`

### 2) 수정 파일: `backend/app/services/geopolitics_mapper.py`
- `map_actions_to_geopolitics()` 시그니처 확장:
  - `source_filter: str | None = None` 파라미터 추가
- 액션 메타데이터 출처 필터링 추가:
  - `metadata.source == "geo_event"` → 매핑 제외
  - `metadata.source == "user_decision"` → 매핑 제외
- 라운드 단위 디바운스 추가:
  - `seen_event_types_this_round`로 동일 `geopolitics_action` 타입 1회만 매핑
- 메타데이터가 없는 기존 액션은 기존 방식으로 그대로 매핑되어 하위 호환 유지

## 검증

- LSP diagnostics 실행:
  - `backend/app/services/context_injection.py`: clean
  - `backend/app/services/geopolitics_mapper.py`: clean
- import/type 오류 없음
