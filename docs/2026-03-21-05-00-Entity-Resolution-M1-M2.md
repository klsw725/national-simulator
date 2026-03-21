# Entity Resolution M1-M2 — PG 스키마 + 매칭 엔진

> 날짜: 2026-03-21 05:00
> PRD: v2-entity-resolution M1-M2

## 프롬프트

```
PRD Next 분석 → v2-entity-resolution M1-M2 추천 → 사용자 "진행" 확인
```

## 변경 사항

### M1: PG 스키마

**backend/app/database.py**:
- `resolution_candidates` 테이블: observation_id, candidate_stix_id, match_score, match_strategy, match_reason, status(pending/accepted/rejected)
- `resolution_decisions` 테이블: observation_id, resolved_stix_id, decision_type(auto/manual_merge/manual_reject), decided_by, confidence, reason
- 5개 인덱스: observation_id, candidate_stix_id, status, decisions.observation_id, decisions.resolved_stix_id

### M2: 매칭 엔진

**backend/app/resolution/matcher.py** (신규):
- `Matcher.find_candidates()` — 관측 데이터에 대해 모든 매칭 전략 실행
- **전략 1: 정확 매칭** — MMSI, IMO, ICAO24, NORAD ID (score: 1.0). stix_objects에서 동일 식별자 검색
- **전략 2: 퍼지 매칭** — SequenceMatcher 기반 이름 유사도 (score: 0.6~0.9). 완벽한 정확 매칭이 없을 때만 실행
- `_EXACT_ID_FIELDS` — source_type별 식별자 필드 매핑 (ship→mmsi/imo, flight→icao24, satellite→norad_id)
- `_SOURCE_TO_STIX_TYPE` — source_type→stix object_type 매핑

**backend/app/resolution/resolver.py** (신규):
- `Resolver.resolve_observation()` — 단일 관측 → 후보 매칭 → resolution_candidates 저장
- `Resolver.resolve_batch()` — 다수 관측 일괄 처리
- `Resolver.get_candidates()` — 저장된 후보 조회 (observation_id, status 필터)
- `Resolver.get_decisions()` — 해소 결정 조회
- Gotham 패턴 준수: observations 테이블은 절대 수정하지 않음 (비파괴적)

## 아키텍처

```
observations (Tier 1, 불변)
    ↓ Matcher.find_candidates()
resolution_candidates (score + strategy)
    ↓ M3에서 자동 해소 (threshold 0.85)
    ↓ M4에서 수동 검토 API
stix_objects (Tier 2) ← resolution_decisions
```

## 잠금 해제

- M3 (자동 해소): 고신뢰도 후보 자동 반영 로직만 추가하면 됨
- M4 (수동 검토 API): 라우터 + accept/reject/merge 엔드포인트만 추가하면 됨
