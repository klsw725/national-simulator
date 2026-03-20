# PRD: 스냅샷 브랜칭

> Status: Draft
> Created: 2026-03-20
> Dependencies: v2-postgresql-postgis
> 관련 스펙: `specs/MVP-SPEC.md` Section 18 (시나리오/라이브 경계), Section 19 (High 리스크)
> 버전: v2.0

---

## 1. 문제 정의

MVP에서 시뮬레이션은 라이브 OSINT 데이터와 같은 DB를 공유한다. 시뮬레이션이 시나리오 데이터를 수정하면 라이브 분석 결과에 영향을 줄 수 있고, 반대로 라이브 데이터 업데이트가 진행 중인 시뮬레이션을 오염시킬 수 있다.

핵심 과제:
- 시뮬레이션 쓰기가 라이브 OSINT 데이터를 변경할 수 있다
- 여러 시나리오가 동시에 실행될 때 데이터 충돌이 발생한다
- 시뮬레이션 결과만 시각화에 투영해야 하는데 경계가 불명확하다
- SPEC §18: 시나리오 브랜치(쓰기 전용)와 라이브 세계(읽기 전용)를 명확히 분리

## 2. 솔루션 개요

- **PG 스냅샷 복제** — 시나리오 시작 시 특정 시점의 라이브 데이터 스냅샷 생성
- **시나리오 브랜치** — 스냅샷 기반 격리된 쓰기 공간
- **라이브 세계 읽기 전용** — 시뮬레이션에서 라이브 데이터 직접 수정 불가
- **투영 레이어** — 시뮬레이션 결과만 시각화에 반영

## 3. 기술 상세

### 3.1 브랜칭 모델

```
live_world (읽기 전용)
    ↓ snapshot_at 시점 복제
scenario_branch_{scenario_id}
    ├── observations_snapshot    # 라이브 데이터 복사본
    ├── stix_objects_snapshot    # 해소된 엔티티 복사본
    └── simulation_writes        # 시뮬레이션 전용 쓰기 공간
```

### 3.2 PG 스키마

`scenario_branches` 핵심 필드: `scenario_id UUID`, `snapshot_at TIMESTAMPTZ`, `branch_schema TEXT` ("branch_{id}"), `status` (active/merged/archived)

각 브랜치는 별도 PG 스키마로 격리. 스냅샷 테이블: `branch_{id}.observations`, `branch_{id}.stix_objects`

### 3.3 스냅샷 생성 프로세스

1. 새 PG 스키마 생성 (`CREATE SCHEMA branch_{scenario_id_hex[:8]}`)
2. 특정 시점 데이터 복사 (`CREATE TABLE branch_X.observations AS SELECT * FROM public.observations WHERE created_at <= $snapshot_at`)
3. 브랜치 메타데이터 기록 (scenario_branches 테이블)

### 3.4 투영 레이어

시각화 API는 두 소스를 병합해서 반환:
- 라이브 세계 현재 상태 (기본 레이어)
- 시나리오 브랜치 시뮬레이션 결과 (오버레이 레이어, scenario_id 파라미터 있을 때만)

### 3.5 수정 대상 파일

```
backend/
├── app/branching/
│   ├── snapshot.py             # 신규: 스냅샷 생성/관리
│   ├── branch_manager.py       # 신규: 브랜치 생명주기
│   └── projection.py           # 신규: 라이브+시뮬레이션 투영
└── alembic/versions/
    └── 0005_scenario_branches.py  # 신규: scenario_branches 테이블
```

## 4. 마일스톤

- [ ] **M1: PG 스키마 격리** — scenario_branches 테이블, 브랜치별 PG 스키마 생성
  - 검증: 시나리오 생성 → 별도 PG 스키마 생성 확인

- [ ] **M2: 스냅샷 복제** — 특정 시점 데이터 복사, MVCC 활용
  - 검증: 스냅샷 생성 후 라이브 데이터 변경 → 브랜치 데이터 불변 확인

- [ ] **M3: 쓰기 격리** — 시뮬레이션 쓰기가 브랜치 스키마에만 반영
  - 검증: 브랜치 내 엔티티 수정 → 라이브 세계 미반영 확인

- [ ] **M4: 투영 레이어** — 시각화 API에서 라이브+시뮬레이션 병합
  - 검증: 시나리오 ID 포함 요청 → 시뮬레이션 오버레이 포함 응답

## 5. 성공 기준

- 시뮬레이션 쓰기가 라이브 OSINT 데이터를 변경하지 않는다
- 여러 시나리오가 동시에 실행되어도 데이터 충돌이 없다
- 시각화에서 라이브 데이터와 시뮬레이션 결과를 구분해서 표시한다
- 브랜치 아카이브 시 PG 스키마가 정리된다

## 6. 위험 및 완화

| 위험 | 완화 |
|------|------|
| 브랜치 스키마 증가로 PG 스토리지 부담 | 브랜치 TTL 설정 (7일 후 자동 아카이브). 스냅샷 압축 |
| 스냅샷 복제 시간이 길어질 수 있음 (대용량 데이터) | 증분 스냅샷 검토. 초기에는 최근 24h 데이터만 복사 |
| PG 스키마 이름 충돌 | scenario_id UUID 기반 스키마 이름으로 충돌 방지 |

## 7. 참고

### 관련 PRD
- **v2-postgresql-postgis** — PG MVCC + 스키마 격리 기반
- **v2-action-layer** — 브랜치 내 조치 실행
- **v2-entity-resolution** — 브랜치별 독립적 해소 결과

### SPEC 근거
- §18 시나리오/라이브 경계: 시뮬레이션이 라이브 데이터를 오염시키지 않는 격리 원칙
- §19 High 리스크: 데이터 오염이 분석 신뢰성을 훼손하는 핵심 위험

## 진행 로그

| 날짜 | 상태 | 내용 |
|------|------|------|
| 2026-03-20 | Draft | v2 스냅샷 브랜칭 PRD 초안 작성 |
