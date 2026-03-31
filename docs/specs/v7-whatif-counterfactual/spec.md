# OSINT Simulator V7 - Technical Specification

> Version: 7.0.0
> Date: 2026-03-23
> Status: Complete
> Codename: **Ghostfish v7** — What-If Counterfactual

---

## 1. Executive Summary

V7은 V4에서 미완으로 남았던 What-If 분기를 MiroFish 제약에 맞춰 실현한 릴리스다. 중간 라운드 포크 대신 수정된 가설을 시드에 주입해 전체 파이프라인을 재실행하는 Counterfactual Replay 전략을 채택했다. 또한 원본/분기 결과를 MAXS-inspired 지표로 정량 비교해, 가설 변경의 효과를 분석 가능한 형태로 제공한다.

### V6 → V7 핵심 차이

| V6 | V7 |
|---------|------|
| 품질/성능 및 시계열 분석 강화 | What-If 분기 실행 모델 확립 |
| 단일 실행 결과 중심 | 원본 vs 분기 시나리오 비교 가능 |
| 가설 검증은 수동 해석 중심 | Counterfactual Replay + 비교 메트릭 자동화 |
| 분기 상태 저장 구조 부재 | whatif_branches 스키마/엔진/API 도입 |

---

## 2. 구성 PRD

V7은 MiroFish의 mid-simulation 제약을 우회하기 위해 full replay 기반 분기 생성, 분기 메타데이터 관리, 정량 비교 지표를 단일 PRD로 통합 설계했다.

---

## PRD 인덱스

| PRD | 설명 | 상태 |
|-----|------|------|
| [v7-whatif-counterfactual.md](prds/v7-whatif-counterfactual.md) | Counterfactual Replay 기반 What-If 분기 생성/실행/비교 | Complete |
