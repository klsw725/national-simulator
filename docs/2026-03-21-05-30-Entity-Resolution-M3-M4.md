# Entity Resolution M3-M4 — 자동 해소 + 수동 검토 API

> 날짜: 2026-03-21 05:30
> PRD: v2-entity-resolution M3-M4

## 프롬프트

```
PRD Next 분석 → v2-entity-resolution M3-M4 추천 → 사용자 "진행" 확인
```

## 변경 사항

### M3: 자동 해소 (resolver.py 확장)

- `AUTO_RESOLVE_THRESHOLD = 0.85` — 이 점수 이상이면 자동 해소
- `Resolver.auto_resolve()` — 매칭 실행 후 고신뢰도 후보 자동 accept + resolution_decisions 기록
- `Resolver._auto_accept()` — 후보 status → 'accepted' + decision 기록
- `Resolver._record_decision()` — resolution_decisions INSERT 헬퍼

### M4: 수동 검토 API

**backend/app/resolution/resolver.py 확장**:
- `accept_candidate(candidate_id, decided_by)` — pending 후보 수락 + decision 기록
- `reject_candidate(candidate_id, decided_by)` — pending 후보 거부 + decision 기록
- `merge_entities(observation_id, target_stix_id, decided_by)` — 직접 병합 (후보 없이)

**backend/app/resolution/router.py (신규)**:
- `GET /api/resolution/queue` — pending 상태 후보 목록 (수동 검토 큐)
- `GET /api/resolution/decisions` — 해소 결정 이력
- `POST /api/resolution/{candidate_id}/accept` — 후보 수락
- `POST /api/resolution/{candidate_id}/reject` — 후보 거부
- `POST /api/resolution/merge` — 직접 병합

**backend/app/main.py**:
- `resolution_router` 등록

## 잠금 해제

- v2-entity-resolution PRD 전체 완료 (M1-M4)
- 정적 military_vessels.json 수동 매핑 → 동적 자동 매칭으로 전환 가능
- OSINT 관측 데이터가 자동/수동으로 stix_objects에 연결
