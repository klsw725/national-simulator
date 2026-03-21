# V4-1 M1: DecisionPoint 모델 + API

> 날짜: 2026-03-21
> PRD: v4-ai-guided-decisions (V4-1)
> 마일스톤: M1

## 프롬프트

```
prd-next → V4-1 M1 추천 → 설계 논의 → 진행
```

## 변경 사항

### 신규 파일

- `backend/app/models/decision_point.py`
  - `DecisionPointType` enum: seed_selection, actor_configuration, parameter_recommendation
  - `DecisionOption` 모델: id, label, description, confidence (0.0-1.0), reasoning, data
  - `DecisionPointCreate` 요청 모델: type, options, recommended, allow_custom
  - `DecisionPointResponse` 응답 모델: 전체 필드 + status, selected_option_id, custom_data
  - `DecisionPointResolveRequest` 모델: selected_option_id 또는 custom_data

### 수정 파일

- `backend/app/database.py`
  - `decision_points` 테이블 추가 (id, scenario_id FK, type, options JSON, recommended, allow_custom, status, selected_option_id, custom_data JSON, created_at, resolved_at)
  - 인덱스 2개: idx_decision_points_scenario, idx_decision_points_status

- `backend/app/routers/simulation.py`
  - `POST /{scenario_id}/decision_points` — 결정 지점 생성 (recommended 옵션 ID 검증)
  - `GET /{scenario_id}/decision_points` — 목록 조회 (status 필터 옵션)
  - `GET /{scenario_id}/decision_points/{dp_id}` — 상세 조회
  - `POST /{scenario_id}/decision_points/{dp_id}/resolve` — 분석관 결정 제출
    - selected_option_id 또는 custom_data 중 하나 필수
    - 이미 resolved면 409
    - allow_custom=false이면 custom_data 거부
    - 옵션 ID 유효성 검증

- `frontend/src/types/simulation.ts`
  - `DecisionOption` 인터페이스
  - `DecisionPointType` 타입 리터럴
  - `DecisionPoint` 인터페이스

- `frontend/src/lib/gatewayApi.ts`
  - `getDecisionPoints(scenarioId, status?)` — 목록 조회
  - `getDecisionPoint(scenarioId, dpId)` — 상세 조회
  - `resolveDecisionPoint(scenarioId, dpId, data)` — 결정 제출

### 설계 결정

- DB 패턴: 기존 asyncpg raw SQL + TEXT JSON 컬럼 패턴 유지
- ID 형식: `dp_{uuid.uuid4().hex[:12]}` (기존 `scn_`, `seed_`, `simr_` 패턴)
- resolve 검증: selected_option_id가 options에 존재하는지 서버 사이드 검증
- allow_custom 처리: false이면 custom_data만으로의 resolve 거부
- ActionLogger 통합: create, resolve 이벤트 감사 로그
