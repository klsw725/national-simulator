# PRD: Action Layer

> Status: Complete
> Created: 2026-03-20
> Dependencies: v2-postgresql-postgis
> 관련 스펙: `specs/MVP-SPEC.md` Section 18 (Layer 3 ACTION LAYER), Section 19 (High 리스크)
> 버전: v2.0

---

## 1. 문제 정의

MVP의 시뮬레이션 결과는 읽기 전용 JSON으로만 저장된다. 시뮬레이션이 실제 데이터(시나리오, 시드, 엔티티)를 변경하려면 직접 DB 쓰기가 필요한데, 이 과정에서 감사 트레일이 없고 롤백이 불가능하다.

핵심 과제:
- 시뮬레이션 결과 → 실제 조치 연결 경로가 없다
- 쓰기 연산의 승인 흐름이 없다 (누가, 언제, 왜 변경했는지 불명)
- 잘못된 조치를 되돌릴 수단이 없다
- SPEC §18 Layer 3: 모든 쓰기 연산을 Action으로 추상화하고 감사 트레일 보장

## 2. 솔루션 개요

- **Action 정의 스키마** — 허용된 조치 유형과 파라미터 명세
- **PG append-only 이벤트 테이블** — 모든 조치를 불변 이벤트로 기록
- **승인 규칙** — 조치 유형별 자동 승인 또는 수동 승인 요구
- **RBAC** — 역할 기반 조치 권한 제어
- **롤백** — 보상 Action으로 이전 상태 복원

## 3. 기술 상세

### 3.1 Action 유형 정의

ActionType enum 목록: `SCENARIO_UPDATE`, `SCENARIO_ARCHIVE`, `ENTITY_TAG`, `ENTITY_MERGE`, `ENTITY_ANNOTATE`, `SEED_INJECT`, `SEED_REMOVE`, `SIMULATION_TRIGGER`

### 3.2 PG append-only 스키마

핵심 필드: `action_type`, `payload JSONB`, `actor_id`, `actor_role` (admin/analyst/system), `status` (pending/approved/rejected/executed/compensated), `compensation_for UUID` (롤백 참조)

append-only 강제: `CREATE RULE no_update AS ON UPDATE TO action_events DO INSTEAD NOTHING` + no_delete 동일 패턴

### 3.3 승인 규칙

자동 승인: `ENTITY_TAG`, `SEED_INJECT`, `SIMULATION_TRIGGER` (analyst 이상)
수동 승인 필요: `ENTITY_MERGE` (analyst), `SCENARIO_ARCHIVE` (admin)

### 3.4 API 인터페이스

```
POST /api/actions                  # 조치 생성 (pending)
GET  /api/actions?status=pending   # 승인 대기 목록
POST /api/actions/{id}/approve     # 승인 + 실행
POST /api/actions/{id}/reject      # 거부
POST /api/actions/{id}/compensate  # 롤백 (보상 Action 생성)
```

### 3.5 수정 대상 파일

```
backend/app/actions/
├── types.py     # 신규: ActionType enum, Action 모델
├── executor.py  # 신규: 조치 실행 로직
├── approver.py  # 신규: 승인 규칙 엔진
└── router.py    # 신규: Action API 엔드포인트
```

## 4. 마일스톤

- [x] **M1: PG 스키마** — action_events 테이블, append-only 규칙 (INSERT만 허용)
  - 검증: INSERT 성공, UPDATE 시도 → 무시 확인

- [x] **M2: Action 타입 + 실행 엔진** — ActionType enum, 타입별 실행 로직
  - 검증: ENTITY_TAG 생성 → 실행 → stix_objects 업데이트 확인

- [x] **M3: 승인 규칙 + RBAC** — 조치 유형별 승인 방식, 역할 검증
  - 검증: analyst가 SCENARIO_ARCHIVE 시도 → 403 반환

- [x] **M4: 롤백** — compensation_for 참조, 보상 조치 실행
  - 검증: ENTITY_TAG 실행 후 compensate → 태그 제거 확인

## 5. 성공 기준

- 모든 쓰기 연산이 action_events 테이블에 기록된다
- action_events는 INSERT만 가능하고 UPDATE/DELETE는 차단된다
- 조치 유형별 승인 규칙이 적용된다
- 보상 Action으로 이전 상태를 복원할 수 있다
- 감사 트레일로 누가 언제 무엇을 변경했는지 추적 가능하다

## 6. 위험 및 완화

| 위험 | 완화 |
|------|------|
| append-only 규칙이 PG Rule로 구현 시 성능 영향 | Row Level Security 또는 트리거로 대체 검토 |
| 보상 Action이 실패할 경우 (부분 롤백) | 보상 실패도 action_events에 기록. 수동 복구 절차 문서화 |
| 승인 대기 조치가 쌓여 병목 발생 | 자동 승인 범위 확대. 만료 시간 설정 (24h 후 자동 거부) |

## 7. 참고

### 관련 PRD
- **v2-postgresql-postgis** — PG append-only 이벤트 테이블 기반
- **v2-entity-resolution** — 해소된 엔티티에 대한 조치 실행
- **v2-snapshot-branching** — 시나리오 브랜치 내 조치 격리

### SPEC 근거
- §18 Layer 3 ACTION LAYER: 쓰기 연산 추상화, 감사 트레일, 승인 흐름
- §19 High 리스크: 감사 불가 쓰기 연산이 데이터 무결성 위협

## 진행 로그

| 날짜 | 상태 | 내용 |
|------|------|------|
| 2026-03-20 | Draft | v2 Action Layer PRD 초안 작성 |
| 2026-03-21 | M3-M4 완료 | 승인 규칙(RBAC) + 역할 검증 + 보상 Action 롤백. APPROVAL_RULES 딕셔너리 기반 auto_approve/manual 분기. 전체 마일스톤 완료 |
