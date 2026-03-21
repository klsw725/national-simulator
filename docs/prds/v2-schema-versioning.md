# PRD: 온톨로지 스키마 버전관리

> Status: Draft
> Created: 2026-03-20
> Dependencies: v2-stix2-ontology
> 관련 스펙: `specs/MVP-SPEC.md` Section 17.1 (팔란티어 스키마 관리 채택)
> 버전: v2.0

---

## 1. 문제 정의

MiroFish는 LLM이 즉석에서 온톨로지를 생성한다. 이 온톨로지는 시뮬레이션마다 조금씩 달라질 수 있고, 시간이 지나면서 진화한다. 버전관리 없이는 이전 시뮬레이션 결과와 현재 온톨로지가 호환되는지 알 수 없다.

핵심 과제:
- LLM 생성 온톨로지가 버전 없이 덮어쓰여진다
- 온톨로지 변경이 기존 시뮬레이션 결과를 깨뜨릴 수 있다
- 어떤 버전의 온톨로지로 어떤 시뮬레이션이 실행됐는지 추적 불가
- SPEC §17.1: 팔란티어 스키마 관리 패턴 채택 — 스키마 변경 이력 + 하위 호환성 검증

## 2. 솔루션 개요

- **스키마 version 필드** — 모든 온톨로지 객체에 버전 번호 부여
- **온톨로지 변경 이력** — 변경 내용과 이유를 PG에 기록
- **하위 호환성 검증** — 새 버전이 기존 데이터를 깨뜨리는지 자동 검사
- **Alembic 연동** — DB 스키마 변경과 온톨로지 버전 변경을 함께 관리

## 3. 기술 상세

### 3.1 버전 체계

```
온톨로지 버전: MAJOR.MINOR.PATCH
- MAJOR: 하위 호환 불가 변경 (필드 제거, 타입 변경)
- MINOR: 하위 호환 가능 추가 (새 필드, 새 SDO 타입)
- PATCH: 설명/메타데이터 변경
```

### 3.2 PG 스키마

`ontology_versions` 핵심 필드: `version TEXT` ("1.2.0"), `schema_hash TEXT`, `schema_json JSONB`, `change_summary`, `is_breaking BOOLEAN`, `created_by`

`simulation_results`에 `ontology_version TEXT` 컬럼 추가 (버전 참조)

### 3.3 하위 호환성 검증 규칙

Breaking 변경: `field_removed`, `field_type_changed`, `required_added`, `sdo_type_removed`

Non-breaking 변경: `field_added_optional`, `sdo_type_added`, `description_changed`

### 3.4 버전 관리 API

```
GET  /api/ontology/versions                          # 버전 목록
POST /api/ontology/versions                          # 새 버전 등록
GET  /api/ontology/versions/diff?from=1.0.0&to=1.1.0 # 버전 간 차이
POST /api/ontology/versions/validate                 # 호환성 검증
```

### 3.5 수정 대상 파일

```
backend/
├── app/ontology/
│   ├── versioning.py           # 신규: 버전 관리, diff, 호환성 검증
│   └── router.py               # 수정: 버전 관리 API 추가
└── alembic/versions/
    └── 0006_ontology_versions.py  # 신규: ontology_versions 테이블
```

## 4. 마일스톤

- [x] **M1: PG 스키마** — ontology_versions 테이블, simulation_results에 버전 참조 추가
  - 검증: `alembic upgrade head` 성공

- [x] **M2: 버전 등록 + diff** — 새 버전 등록 API, 버전 간 차이 계산
  - 검증: 두 스키마 비교 → 변경 목록 반환

- [x] **M3: 하위 호환성 검증** — CompatibilityChecker 구현, breaking 변경 감지
  - 검증: 필드 제거 → is_breaking=True 자동 설정

- [x] **M4: MiroFish 연동** — 온톨로지 생성 시 자동 버전 등록
  - 검증: 시뮬레이션 실행 → simulation_results에 ontology_version 기록

## 5. 성공 기준

- 모든 온톨로지 변경이 ontology_versions에 기록된다
- 하위 호환 불가 변경이 자동으로 감지되고 표시된다
- 시뮬레이션 결과가 어떤 온톨로지 버전으로 생성됐는지 추적 가능하다
- 버전 간 diff API로 변경 내용을 확인할 수 있다

## 6. 위험 및 완화

| 위험 | 완화 |
|------|------|
| LLM이 매번 미묘하게 다른 온톨로지를 생성해 버전이 폭발적으로 증가 | 스키마 해시 비교로 실질적 변경 없으면 새 버전 생성 안 함 |
| 하위 호환성 검증이 너무 엄격해 정상 변경도 차단 | 검증은 경고만 발생. 강제 차단은 MAJOR 버전 변경 시만 |
| 오래된 버전 데이터 조회 성능 | 버전별 스키마 캐싱. 자주 쓰는 버전 인덱싱 |

## 7. 참고

### 관련 PRD
- **v2-stix2-ontology** — 커스텀 SDO 스키마 진화 추적
- **v2-postgresql-postgis** — Alembic 마이그레이션 연동

### SPEC 근거
- §17.1: 팔란티어 스키마 관리 패턴 — 스키마 변경 이력, 하위 호환성 검증, 버전 참조
- §18 Layer 2 ONTOLOGY: LLM 즉석 생성 온톨로지의 안정화 필요성

## 진행 로그

| 날짜 | 상태 | 내용 |
|------|------|------|
| 2026-03-20 | Draft | v2 온톨로지 스키마 버전관리 PRD 초안 작성 |
| 2026-03-21 | M1-M3 완료 | PG 스키마 + 버전 등록/diff API + 호환성 검증 |
| 2026-03-21 | M4 완료 | SimulationOrchestrator에서 ontology 단계 후 자동 버전 등록 + simulation_results.ontology_version 기록. 전체 마일스톤 완료 |
