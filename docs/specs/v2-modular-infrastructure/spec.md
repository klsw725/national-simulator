# OSINT Simulator V2 - Technical Specification

> Version: 2.0.0
> Date: 2026-03-20
> Status: Complete
> Codename: **Ghostfish v2** — Modular Infrastructure

---

## 1. Executive Summary

V2는 MVP의 단일/정적 구조를 확장 가능한 모듈형 인프라로 전환한 버전이다. PostgreSQL+PostGIS 전환을 기반으로 STIX2 온톨로지, Entity Resolution, Action Layer, 스키마 버전관리, 스냅샷 브랜칭을 도입해 데이터 무결성과 추적 가능성을 확보했다. 동시에 OASIS 서브클래싱과 지정학 시나리오 엔진을 결합해 지정학 시뮬레이션 코어를 구축했고, 체크포인트/실시간 모니터링으로 운영 가시성을 높였다.

### V1 → V2 핵심 차이

| V1 | V2 |
|---------|------|
| SQLite 기반 단일 저장소 | PostgreSQL+PostGIS 기반 확장형 데이터 레이어 |
| 비정형 온톨로지/정적 매핑 중심 | STIX2 표준화 + Entity Resolution + 스키마 버전관리 |
| 쓰기 감사/승인/롤백 체계 부재 | Action Layer 기반 append-only 감사/승인/보상 처리 |
| 라이브/시나리오 경계 불명확 | 스냅샷 브랜칭으로 시뮬레이션 격리 |
| 일괄 실행 중심 파이프라인 | 체크포인트 모드 + 실시간 모니터링 제공 |

---

## 2. 구성 PRD

V2는 인프라(데이터베이스/표준화/버전관리), 실행 제어(Action/체크포인트/브랜칭), 시뮬레이션 코어(OASIS 확장/지정학 엔진), 운영 가시성(실시간 모니터링)을 10개 PRD로 분할해 구축했다.

---

## PRD 인덱스

| PRD | 설명 | 상태 |
|-----|------|------|
| [v2-postgresql-postgis.md](prds/v2-postgresql-postgis.md) | PostgreSQL+PostGIS 마이그레이션 및 공간 인덱스 기반 구축 | Complete |
| [v2-action-layer.md](prds/v2-action-layer.md) | Action 이벤트 기반 승인/감사/롤백 레이어 | Complete |
| [v2-entity-resolution.md](prds/v2-entity-resolution.md) | 비파괴적 Entity Resolution 및 수동 검토 흐름 | Complete |
| [v2-schema-versioning.md](prds/v2-schema-versioning.md) | 온톨로지 버전관리와 하위 호환성 검증 | Complete |
| [v2-geopolitics-scenario-engine.md](prds/v2-geopolitics-scenario-engine.md) | 지정학 상태 전이/이벤트 전파 코어 엔진 | Complete |
| [v2-oasis-platform-subclassing.md](prds/v2-oasis-platform-subclassing.md) | OASIS GeopoliticsPlatform 서브클래싱 | Complete |
| [v2-pipeline-checkpoints.md](prds/v2-pipeline-checkpoints.md) | 단계별 검토 가능한 파이프라인 체크포인트 모드 | Complete |
| [v2-realtime-monitoring.md](prds/v2-realtime-monitoring.md) | 라이브 액션/통계 기반 실시간 모니터링 | Complete |
| [v2-snapshot-branching.md](prds/v2-snapshot-branching.md) | 시나리오 브랜치 스냅샷 격리 및 투영 레이어 | Complete |
| [v2-stix2-ontology.md](prds/v2-stix2-ontology.md) | STIX2 2-Tier 온톨로지 표준화 | Complete |
