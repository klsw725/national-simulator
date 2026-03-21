# PRD: stix2 온톨로지 표준화

> Status: Draft
> Created: 2026-03-20
> Dependencies: v2-postgresql-postgis
> 관련 스펙: `specs/MVP-SPEC.md` Section 17.2 (OpenCTI 대신 stix2), Section 18 (Layer 2 ONTOLOGY)
> 버전: v2.0

---

## 1. 문제 정의

MVP의 온톨로지는 MiroFish가 즉석에서 생성하는 비정형 JSON이다. 엔티티 간 관계, 타입 검증, 표준 식별자가 없어서 Entity Resolution과 Action Layer 구현이 불가능하다.

핵심 과제:
- OSINT 엔티티(선박, 항공기, 위성 등)에 표준 식별자 체계가 없다
- 관측(observation)과 해소된 엔티티(resolved entity)가 구분되지 않는다
- 온톨로지 변경 시 기존 데이터와의 호환성 검증 수단이 없다
- SPEC §17.2: OpenCTI 전체 스택 도입 대신 stix2 Python 라이브러리만 채택

## 2. 솔루션 개요

- **2-Tier 온톨로지 구조** — Tier 1(원시 관측, Native PG) + Tier 2(STIX-aligned 해소 엔티티)
- **stix2 커스텀 SDO** — x-vessel, x-aircraft, x-satellite 커스텀 STIX Domain Object 정의
- **PG Tier 2 테이블** — 해소된 엔티티를 STIX 형식으로 저장
- **STIX 검증 레이어** — 엔티티 생성/수정 시 stix2 라이브러리로 유효성 검증

## 3. 기술 상세

### 3.1 2-Tier 온톨로지 구조

```
Tier 1 (원시 관측)          Tier 2 (해소된 엔티티)
─────────────────────       ──────────────────────────
observations 테이블          stix_objects 테이블
- raw SB 데이터              - STIX SDO JSON (JSONB)
- 타임스탬프, 소스           - stix_id, object_type
- 좌표 (geom)                - confidence, provenance_ids[]
```

### 3.2 커스텀 STIX SDO 목록

- `x-vessel` — 선박 (MMSI, IMO, 국적, 선종)
- `x-aircraft` — 항공기 (ICAO24, 콜사인, 군용 여부)
- `x-satellite` — 위성 (NORAD ID, 궤도 유형, 국가)
- `x-geopolitical-actor` — 국가/비국가 행위자

stix2 `@CustomObject` 데코레이터로 정의. 필수 필드 누락/타입 불일치 시 라이브러리가 자동 검증.

### 3.3 PG Tier 2 스키마

`stix_objects` 핵심 필드: `stix_id TEXT UNIQUE` ("x-vessel--uuid"), `object_type`, `stix_json JSONB`, `confidence FLOAT`, `provenance_ids UUID[]`

인덱스: `object_type`, `stix_id`

### 3.4 수정 대상 파일

```
backend/
├── app/ontology/
│   ├── custom_sdo.py          # 신규: x-vessel, x-aircraft 등 커스텀 SDO
│   ├── validator.py           # 신규: StixValidator
│   └── tier2_repository.py   # 신규: stix_objects CRUD
└── alembic/versions/
    └── 0002_stix_tier2.py    # 신규: stix_objects 테이블
```

## 4. 마일스톤

- [x] **M1: 커스텀 SDO 정의** — stix2 라이브러리 설치, x-vessel/x-aircraft/x-satellite SDO 구현
  - 검증: `XVessel(name="test", mmsi="123456789")` 생성 성공, STIX JSON 직렬화 확인

- [x] **M2: PG Tier 2 테이블** — Alembic 마이그레이션으로 stix_objects 테이블 생성
  - 검증: `alembic upgrade head` 성공, 인덱스 생성 확인

- [x] **M3: STIX 검증 레이어** — StixValidator 구현, API 엔드포인트에 검증 통합
  - 검증: 잘못된 STIX 객체 생성 시 422 에러 반환

- [x] **M4: MiroFish 온톨로지 연동** — MiroFish 생성 온톨로지를 Tier 2 형식으로 변환하는 어댑터
  - 검증: 시뮬레이션 결과 → stix_objects 저장 성공

## 5. 성공 기준

- x-vessel, x-aircraft, x-satellite SDO가 stix2 라이브러리로 생성/검증된다
- stix_objects 테이블에 STIX JSON이 저장되고 stix_id로 조회된다
- 잘못된 STIX 객체는 저장 전에 거부된다
- Entity Resolution PRD가 이 Tier 2 테이블을 기반으로 구현 가능하다

## 6. 위험 및 완화

| 위험 | 완화 |
|------|------|
| stix2 커스텀 SDO 스펙 변경 시 기존 데이터 호환성 | v2-schema-versioning PRD와 연동. 스키마 변경 시 마이그레이션 필수 |
| MiroFish 즉석 생성 온톨로지가 STIX 구조와 맞지 않을 수 있음 | 어댑터 레이어에서 best-effort 매핑. 매핑 실패 시 raw JSON으로 fallback |
| stix2 라이브러리 Python 버전 의존성 | uv로 버전 고정. requirements 충돌 사전 확인 |

## 7. 참고

### 관련 PRD
- **v2-postgresql-postgis** — Tier 2 PG 테이블 기반
- **v2-entity-resolution** — Tier 2 stix_objects를 입력으로 사용
- **v2-schema-versioning** — 커스텀 SDO 스키마 진화 추적

### SPEC 근거
- §17.2: OpenCTI 전체 스택 대신 stix2 Python 라이브러리만 채택 (의존성 최소화)
- §18 Layer 2 ONTOLOGY: 2-Tier 구조 설계 원칙
- §19: 온톨로지 표준화 없이 Entity Resolution 불가 (High 리스크)

## 진행 로그

| 날짜 | 상태 | 내용 |
|------|------|------|
| 2026-03-20 | Draft | v2 온톨로지 표준화 PRD 초안 작성 |
