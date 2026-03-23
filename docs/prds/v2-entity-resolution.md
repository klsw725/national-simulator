# PRD: Entity Resolution

> Status: Complete
> Created: 2026-03-20
> Dependencies: v2-postgresql-postgis, v2-stix2-ontology
> 관련 스펙: `specs/MVP-SPEC.md` Section 20 (Entity Resolution 설계), Section 19 (High 리스크)
> 버전: v2.0

---

## 1. 문제 정의

MVP는 `military_vessels.json` 정적 파일로 선박 신원을 매핑한다. 이 방식은 세 가지 근본적 한계가 있다.

핵심 과제:
- 정적 매핑은 새로운 관측 데이터를 반영하지 못한다 (수동 업데이트 필요)
- 동일 엔티티가 다른 소스에서 다른 식별자로 나타날 때 중복 처리 불가
- 매핑 근거(어떤 관측에서 어떤 엔티티로 해소됐는지)가 추적되지 않는다
- SPEC §20: Gotham 패턴 — 비파괴적 해소 (원본 관측 보존, 해소 결과 별도 저장)

## 2. 솔루션 개요

- **ResolutionBag 모델** — 관측 → 후보 엔티티 매핑 컨테이너
- **후보 매칭 테이블** — 신뢰도 점수와 함께 후보 목록 저장
- **수동 병합/해제 API** — 분석가가 자동 해소 결과를 검토하고 수정
- **출처 추적** — 모든 해소 결정의 근거 기록
- **비파괴적 원칙** — 원본 관측 데이터는 절대 수정하지 않음

## 3. 기술 상세

### 3.1 Gotham 패턴 구조

```
observations (Tier 1)
    ↓ 자동 매칭 (MMSI, ICAO24, NORAD ID)
resolution_candidates
    ↓ 신뢰도 임계값 초과 시 자동 해소
    ↓ 임계값 미달 시 수동 검토 큐
stix_objects (Tier 2)  ←  resolution_decisions
```

### 3.2 PG 스키마

`resolution_candidates`: `observation_id`, `candidate_stix_id`, `match_score FLOAT`, `match_reason JSONB`, `status` (pending/accepted/rejected)

`resolution_decisions`: `observation_id`, `resolved_stix_id`, `decision_type` (auto/manual_merge/manual_reject), `decided_by`, `confidence FLOAT`, `created_at`

### 3.3 매칭 전략 (우선순위 순)

1. **정확 매칭** — MMSI, IMO, ICAO24, NORAD ID (score: 1.0)
2. **퍼지 매칭** — 선박명 유사도, 국적+선종 조합 (score: 0.6~0.9)
3. **공간 근접** — 동일 시간대 동일 위치 (score: 0.4~0.7)
4. **미해소** — 후보 없음 → 신규 stix_object 생성

### 3.4 API + 수정 대상 파일

```
GET  /api/resolution/queue              # 수동 검토 대기 목록
POST /api/resolution/{id}/accept|reject # 수락/거부
POST /api/resolution/merge              # 두 엔티티 수동 병합

backend/app/resolution/
├── matcher.py   # 신규: 매칭 전략
├── resolver.py  # 신규: ResolutionBag, 자동 해소
└── router.py    # 신규: 수동 검토 API
```

## 4. 마일스톤

- [x] **M1: PG 스키마** — resolution_candidates, resolution_decisions 테이블
  - 검증: `alembic upgrade head` 성공

- [x] **M2: 매칭 엔진** — 정확 매칭 (MMSI/ICAO24) + 퍼지 매칭
  - 검증: 테스트 관측 데이터 → 후보 목록 생성 확인

- [x] **M3: 자동 해소** — 신뢰도 임계값(0.85) 초과 시 stix_objects 자동 반영
  - 검증: 고신뢰도 매칭 → stix_object 자동 업데이트

- [x] **M4: 수동 검토 API** — 큐 조회, 수락/거부, 병합 엔드포인트
  - 검증: API 호출 → resolution_decisions 기록 생성

## 5. 성공 기준

- 관측 데이터가 자동으로 stix_objects와 매핑된다 (고신뢰도 케이스)
- 저신뢰도 후보는 수동 검토 큐에 쌓인다
- 모든 해소 결정의 근거가 resolution_decisions에 기록된다
- 원본 observations 테이블은 수정되지 않는다 (비파괴적 원칙)

## 6. 위험 및 완화

| 위험 | 완화 |
|------|------|
| 퍼지 매칭 오탐 | 임계값 보수적으로 설정 (0.85). 수동 검토 큐 적극 활용 |
| 대량 관측 데이터 매칭 성능 | PG 인덱스 최적화. 비동기 배치 처리 |
| 해소 결정 롤백 | resolution_decisions append-only. 롤백은 새 결정으로 덮어씀 |

## 7. 참고

### 관련 PRD
- **v2-postgresql-postgis**, **v2-stix2-ontology**, **v2-action-layer**

### SPEC 근거
- §20: Gotham 패턴 — 비파괴적 해소, 출처 추적, 수동 병합 API
- §19 High 리스크: 정적 매핑으로는 동적 OSINT 환경 대응 불가

## 진행 로그

| 날짜 | 상태 | 내용 |
|------|------|------|
| 2026-03-20 | Draft | v2 Entity Resolution PRD 초안 작성 |
| 2026-03-21 | M1-M2 완료 | PG 스키마(resolution_candidates/decisions 테이블+인덱스) + 매칭 엔진(정확/퍼지). Matcher + Resolver 클래스 |
| 2026-03-21 | M3-M4 완료 | 자동 해소(threshold 0.85) + 수동 검토 API(queue/accept/reject/merge). 전체 마일스톤 완료 |
