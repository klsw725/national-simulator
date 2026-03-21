# OASIS Platform 서브클래싱 M1-M3

> 날짜: 2026-03-21 07:00
> PRD: v2-oasis-platform-subclassing M1-M3

## 프롬프트

```
PRD Next → v2-geopolitics-scenario-engine 완료 후 → OASIS 서브클래싱 진행
사용자: "내부 mirofish code 수정해" → "external 폴더 하위"
```

## 변경 사항

### M1: GeopoliticsActionType (external/.../platforms/geopolitics_actions.py 신규)

- `GeopoliticsActionType(str, Enum)` — 12개 지정학 전용 액션:
  - 외교: DIPLOMATIC_STATEMENT, OFFICIAL_RESPONSE, TREATY_SIGN
  - 군사: MILITARY_MOVEMENT, MILITARY_EXERCISE
  - 경제: SANCTION_IMPOSE, SANCTION_LIFT, TRADE_RESTRICTION
  - 동맹: ALLIANCE_SUPPORT, TACIT_APPROVAL, DIPLOMATIC_ENGAGEMENT
  - 관망: STRATEGIC_OBSERVATION
- `SOCIAL_TO_GEOPOLITICS` — OASIS 소셜 액션 → 지정학 액션 매핑
- `GEOPOLITICS_ACTION_LABELS_EXTENDED` — 한국어 레이블

### M2: GeopoliticsPlatform (external/.../platforms/geopolitics_platform.py 신규)

- OASIS Platform 서브클래스 (try/except으로 OASIS 미설치 시 standalone 동작)
- 12개 async 액션 핸들러 — OASIS `getattr(self, action.value)` 디스패치 호환
- `_record_event()` — 내부 이벤트 로그 저장
- `set_round()` / `get_events()` / `clear_events()` — 라운드 관리

### M3: DB 테이블 + 기존 코드 통합

**backend/app/database.py**:
- `geopolitics_events` 테이블: scenario_id, simulation_result_id, action_type, actor_id, target_actor_ids, content, magnitude, round_number
- 3개 인덱스: scenario, actor_id, action_type

**external/.../platforms/geopolitics.py 수정**:
- `GEOPOLITICS_ACTION_MAP`과 `GEOPOLITICS_ACTION_LABELS`를 `geopolitics_actions.py`에서 import하도록 통합
- 기존 `map_actions_to_geopolitics()`, `build_geopolitics_profile()` 함수 호환 유지

## M4 보류 사유

M4(통합 테스트)는 OASIS 런타임이 설치된 환경에서 GeopoliticsPlatform을 OasisEnv에 주입하여 전체 시뮬레이션을 실행해야 한다. 현재 환경에 OASIS가 설치되어 있지 않아 런타임 검증 불가.
