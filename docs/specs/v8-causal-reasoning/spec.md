# OSINT Simulator V8 - Technical Specification

> Version: 8.0.0
> Date: 2026-03-29
> Status: Draft
> Codename: **Ghostfish v8** — Causal Reasoning

---

## 1. Executive Summary

V8는 기존 규칙/결과 비교 중심 분석을 공식 인과추론 체계로 전환하기 위한 3단계 로드맵이다. 인과 DAG 기반 구축(V8.1), DoWhy GCM 기반 개입·반사실·귀속 엔진(V8.2), LLM 하이브리드 인과 추출과 내러티브 통합(V8.3)을 통해 "왜"와 "만약"을 정량적으로 설명하는 것을 목표로 한다. 현재 3개 PRD 모두 Draft 상태로, 구현 설계와 통합 경로가 정의된 단계다.

### V7 → V8 핵심 차이

| V7 | V8 |
|---------|------|
| Counterfactual Replay 중심 휴리스틱 비교 | DAG+SCM 기반 형식적 인과 추론 |
| 분기 결과 지표 해석 위주 | do-calculus 개입/반사실/귀속 API 계획 |
| 텍스트 인과 추출 체계 부재 | LLM 가설+통계 검증 하이브리드 추출 |
| 브리핑/코파일럿 인과 설명 제한적 | 인과 경로 기반 내러티브 통합 |

---

## 2. 구성 PRD

V8은 인과 데이터 토대(DAG·로그 수집) → 추론 엔진(개입/반사실/귀속) → 사용자 전달층(온톨로지 인과 엣지·브리핑·코파일럿) 순으로 의존성을 갖는 3개 PRD로 구성된다.

---

## PRD 인덱스

| PRD | 설명 | 상태 |
|-----|------|------|
| [v8-causal-dag.md](prds/v8-causal-dag.md) | 도메인/학습 DAG 구축 및 인과 로그 수집 기반 | Draft |
| [v8-causal-reasoner.md](prds/v8-causal-reasoner.md) | DoWhy GCM 기반 개입·반사실·인과 귀속 엔진 | Draft |
| [v8-causal-narrator.md](prds/v8-causal-narrator.md) | LLM 하이브리드 인과 추출 및 인과 내러티브 통합 | Draft |
