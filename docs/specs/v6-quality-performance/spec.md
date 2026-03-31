# OSINT Simulator V6 - Technical Specification

> Version: 6.0.0
> Date: 2026-03-22
> Status: Complete
> Codename: **Ghostfish v6** — Quality & Performance

---

## 1. Executive Summary

V6는 기능 확장보다 운영 품질과 성능 안정화를 목표로, 에러 처리 표준화·프론트엔드 렌더링 최적화·백엔드 쿼리 최적화를 집중 수행했다. 동시에 OSINT 시계열 분석 레이어를 추가해 단일 시점 관측을 시간축 기반 트렌드/이상탐지 분석으로 확장했다. 결과적으로 시스템은 더 빠르고 안정적이면서, 분석관에게 시계열 인사이트를 제공하는 운영형 플랫폼으로 강화됐다.

### V5 → V6 핵심 차이

| V5 | V6 |
|---------|------|
| 인과 추론 확장 중심 로드맵 | 품질/성능 최적화 중심 릴리스 |
| 일부 사일런트 폴백/에러 가시성 부족 | API·프론트 에러 상태 표준화 |
| 폴링/지도 렌더링 비용 높음 | useReducer 통합, Map 최적화, 코드 스플리팅 |
| 포인트 인타임 OSINT 조회 중심 | 시계열 집계/트렌드/이상탐지 API 추가 |

---

## 2. 구성 PRD

V6는 품질·성능 기술부채를 정리하는 핵심 PRD와, OSINT 시계열 데이터 레이어/분석 API/차트 UI를 추가하는 PRD로 구성된다.

---

## PRD 인덱스

| PRD | 설명 | 상태 |
|-----|------|------|
| [v6-quality-performance.md](prds/v6-quality-performance.md) | 에러 핸들링 표준화, 프론트엔드/백엔드 성능 최적화 | Complete |
| [v6-timeseries-analysis.md](prds/v6-timeseries-analysis.md) | OSINT 시계열 집계, 트렌드/이상탐지 API, 차트 시각화 | Complete |
