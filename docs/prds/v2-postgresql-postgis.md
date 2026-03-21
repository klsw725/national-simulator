# PRD: PostgreSQL + PostGIS 마이그레이션

> Status: Draft
> Created: 2026-03-20
> Dependencies: MVP 완료 (PRD 1-6c)
> 관련 스펙: `specs/MVP-SPEC.md` Section 14 (v2 로드맵), Section 19 (Oracle 리뷰 High 리스크)
> 버전: v2.0

---

## 1. 문제 정의

MVP는 SQLite + aiosqlite로 구현되어 있다. v2 고급 기능들이 요구하는 조건을 충족하지 못한다.

핵심 과제:
- Entity Resolution은 그래프 탐색 쿼리와 인덱스가 필요하다 (SQLite 한계)
- Action Layer는 append-only 이벤트 테이블과 트랜잭션 격리가 필요하다
- 스냅샷 브랜칭은 PG의 MVCC와 스키마 격리에 의존한다
- 공간 쿼리 (반경 내 엔티티, 경로 교차)는 PostGIS 없이 불가능하다
- Oracle 리뷰 §19: High 리스크 4개가 모두 PG를 전제로 한다

## 2. 솔루션 개요

- **PG Docker 서비스 추가** — docker-compose.yml에 postgis/postgis:16-3.4 서비스 추가
- **Alembic 마이그레이션** — 스키마 버전관리 도구 도입, 초기 마이그레이션 작성
- **asyncpg 전환** — aiosqlite 제거, asyncpg + SQLAlchemy async 엔진으로 교체
- **PostGIS 확장 활성화** — 공간 인덱스 + 지리 쿼리 지원
- **기존 스키마 이식** — scenarios, seeds, simulation_results 테이블 PG로 이전

## 3. 기술 상세

### 3.1 Docker Compose 변경

```yaml
postgres:
  image: postgis/postgis:16-3.4
  environment:
    POSTGRES_DB: osint_simulator
    POSTGRES_USER: osint
    POSTGRES_PASSWORD: ${PG_PASSWORD}
  volumes: [pgdata:/var/lib/postgresql/data]
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U osint"]
```

### 3.2 asyncpg 전환 포인트

- `aiosqlite.connect()` → `asyncpg.create_pool()`
- SQLite `?` 플레이스홀더 → PG `$1, $2` 형식
- `AUTOINCREMENT` → `GENERATED ALWAYS AS IDENTITY`
- `TEXT` JSON 컬럼 → `JSONB`

### 3.3 PostGIS 공간 인덱스

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
ALTER TABLE observations ADD COLUMN geom geometry(Point, 4326);
CREATE INDEX idx_observations_geom ON observations USING GIST(geom);
```

### 3.4 수정 대상 파일

```
backend/
├── docker-compose.yml     # postgres 서비스 추가
├── .env.example           # PG_PASSWORD, DATABASE_URL 추가
├── app/database.py        # asyncpg 풀 초기화
├── app/repositories/      # SQL 플레이스홀더 전환
└── alembic/               # 신규: 마이그레이션 디렉토리
```

## 4. 마일스톤

- [x] **M1: Docker + PG 서비스** — docker-compose.yml 수정, PG 컨테이너 기동
  - 검증: `docker compose up postgres` 성공, healthcheck 통과

- [x] **M2: Alembic 초기화 + 초기 마이그레이션** — alembic init, 기존 스키마 이식
  - 검증: `alembic upgrade head` 성공, 테이블 생성 확인

- [x] **M3: asyncpg 전환** — database.py, repositories 전체 플레이스홀더 교체
  - 검증: 기존 API 엔드포인트 전체 정상 응답

- [x] **M4: PostGIS 확장 + 공간 인덱스** — 확장 활성화, observations geom 컬럼 추가
  - 검증: `SELECT PostGIS_Version()` 성공

## 5. 성공 기준

- 기존 MVP 기능 전체가 PG 백엔드에서 regression 없이 동작한다
- `alembic upgrade head` 한 번으로 전체 스키마가 생성된다
- PostGIS 공간 쿼리 (`ST_DWithin`, `ST_Intersects`)가 실행 가능하다
- Entity Resolution, Action Layer, 스냅샷 브랜칭 PRD가 이 기반 위에서 구현 가능하다

## 6. 위험 및 완화

| 위험 | 완화 |
|------|------|
| SQLite → PG SQL 방언 차이 (JSON 함수, 날짜 처리) | 마이그레이션 전 SQL 쿼리 전수 검토. JSONB 연산자 차이 문서화 |
| 개발 환경 Docker 의존성 증가 | docker-compose.override.yml로 로컬/CI 분리 |
| Alembic 마이그레이션 충돌 (팀 개발 시) | 브랜치별 마이그레이션 번호 규칙 수립 |

## 7. 참고

### 관련 PRD
- **v2-entity-resolution**, **v2-action-layer**, **v2-snapshot-branching**, **v2-stix2-ontology** — 모두 이 기반에 의존

### Oracle 리뷰 근거 (SPEC §19)
- High 리스크 #1~4: Entity Resolution, 감사 트레일, 데이터 격리, 온톨로지 버전관리 모두 PG 전제

## 진행 로그

| 날짜 | 상태 | 내용 |
|------|------|------|
| 2026-03-20 | Draft | v2 기반 인프라 PRD 초안 작성 |
| 2026-03-21 | M4 완료 | PostGIS 확장 활성화 + observations 테이블(Tier 1, geom 컬럼) + GIST 공간 인덱스. 전체 마일스톤 완료 |
