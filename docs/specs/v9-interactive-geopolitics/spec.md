# OSINT Simulator V9 - Technical Specification

> Version: 9.0.0
> Date: 2026-03-30
> Status: Draft
> Codename: **Ghostfish v9** — Interactive Geopolitics

---

## 1. Executive Summary

V9는 사후 일괄 처리되던 지정학 분석을 라운드 단위 개입 가능한 흐름으로 전환하는 인터랙티브 지정학 설계다. `auto` 모드 하위호환을 유지하면서 `ACTOR_ROLE`, `GAME_MASTER` 듀얼 모드를 도입해 이벤트 기반 일시정지, DecisionPoint 생성, 사용자 선택 반영 후 재개를 지원한다. 핵심은 엔진 규칙을 바꾸지 않고 상태/행동 오버라이드와 스냅샷 복원으로 상호작용성을 확보하는 것이다.

### V8 → V9 핵심 차이

| V8 | V9 |
|---------|------|
| 인과추론 역량 설계/구축 중심 | 지정학 실행 단계의 사용자 개입 UX 강화 |
| 지정학 라운드 일괄 실행 중심 | 라운드 단위 pause/resume + 스냅샷 복원 |
| DecisionPoint 활용 범위 제한적 | 지정학 대응/방향 결정 타입 확장 |
| 자동 의사결정 고정 | actor 행동 오버라이드, 방향별 state delta 반영 |

---

## 2. 구성 PRD

V9는 듀얼 모드 인터랙션, 지정학 스냅샷 영속화, DecisionPoint 확장, 오케스트레이터 pause/continue 경로를 단일 PRD로 통합한다.

---

## PRD 인덱스

| PRD | 설명 | 상태 |
|-----|------|------|
| [v9-interactive-geopolitics.md](prds/v9-interactive-geopolitics.md) | ACTOR_ROLE/GAME_MASTER 듀얼 모드 기반 인터랙티브 지정학 | Draft |
