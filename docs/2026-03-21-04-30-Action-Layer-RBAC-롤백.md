# Action Layer M3-M4 — 승인 규칙(RBAC) + 롤백

> 날짜: 2026-03-21 04:30
> PRD: v2-action-layer M3-M4

## 프롬프트

```
PRD Next 분석 → v2-action-layer M3-M4 추천 → 사용자 "진행" 확인
```

## 변경 사항

### backend/app/database.py

- `action_log` 테이블에 3개 컬럼 추가: `actor_role`, `status`, `compensation_for`
- `ALTER TABLE ADD COLUMN IF NOT EXISTS` 구문으로 기존 DB 호환

### backend/app/services/action_logger.py

전면 재작성 — ActionLogger에 RBAC + 승인 + 보상 로직 추가:

1. **APPROVAL_RULES 딕셔너리** — 액션 타입별 승인 모드(`auto_approve`/`manual`)와 최소 역할(`min_role`) 정의
2. **ROLE_LEVEL 계층** — `viewer(0) < analyst(1) < admin(2) < system(3)`
3. **submit()** — 새 진입점. RBAC 검증 후 auto_approve이면 즉시 실행, manual이면 pending 상태로 생성
4. **approve() / reject()** — pending 상태 액션의 승인/거부. 결정 자체도 이벤트로 기록
5. **compensate()** — 실행된 액션의 롤백. 원본을 `compensated`로 마킹하고 보상 이벤트 생성 (`compensation_for` 참조)
6. **log()** — 기존 호환 유지. 시스템/내부 액션은 승인 없이 즉시 실행

### backend/app/routers/actions.py (신규)

5개 엔드포인트:
- `POST /api/actions` — 액션 생성 (RBAC 검증, 403 on 권한 부족)
- `GET /api/actions?status=pending` — 승인 대기 큐
- `POST /api/actions/{id}/approve` — 승인 + 실행
- `POST /api/actions/{id}/reject` — 거부
- `POST /api/actions/{id}/compensate` — 보상 Action으로 롤백

### backend/app/main.py

- `actions` 라우터 등록

## 승인 규칙 요약

| 액션 타입 | 모드 | 최소 역할 |
|-----------|------|-----------|
| scenario.create/delete | auto_approve | analyst |
| entity.tag/annotate | auto_approve | analyst |
| seed.inject/generate | auto_approve | analyst |
| simulation.start/continue/trigger | auto_approve | analyst |
| entity.merge | manual (큐) | analyst |
| seed.remove | manual (큐) | analyst |
| scenario.archive/update | auto_approve | admin |

## 잠금 해제

- v2-action-layer PRD 전체 완료 (M1-M4)
- Entity Resolution의 수동 병합/해제가 감사 트레일과 함께 동작 가능
- 모든 쓰기 연산에 역할 기반 권한 제어 + 롤백 안전망
