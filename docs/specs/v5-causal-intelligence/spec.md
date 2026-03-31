# OSINT Simulator V5 - Technical Specification

> Version: 5.0.0
> Date: 2026-03-29
> Status: Draft
> Codename: **Ghostfish v5** — Causal Intelligence

---

## 1. Executive Summary

V4에서 구축한 Analyst-in-the-Loop 시스템(AI 가이드 결정 지점, 인터랙티브 시뮬레이션, What-If 분기, AI 코파일럿)은 **분석관이 시뮬레이션에 개입하고 대안 시나리오를 탐색할 수 있게 했다.** 그러나 시스템은 "무엇이 일어났는가"만 보여줄 뿐 **"왜 일어났는가"와 "특정 개입이 결과를 어떻게 바꾸는가"에 대한 형식적 인과 추론 능력이 없다.**

V5의 핵심 목표: **시뮬레이션 데이터에서 인과 구조를 추출·학습하고, do-calculus 기반 개입 쿼리와 반사실 추론을 수행하여 "왜"와 "만약"에 정량적으로 답하는 Causal Intelligence 레이어를 구축한다.**

### V4 → V5 핵심 차이

| V4 | V5 |
|----|-----|
| What-If: 시드 수정 후 전체 재실행 → 커브 비교 | What-If: 인과 귀속으로 "어떤 요인이 차이의 N%를 설명" |
| 지정학 엔진: 규칙 기반 if-then 상태 전이 | 동일 규칙을 공식 인과 DAG (SCM)으로 표현 + 통계 검증 |
| 브리핑: LLM이 서술적으로 "인과관계" 기술 | 브리핑: 검증된 인과 경로 기반 정량적 설명 |
| 코파일럿: 텍스트 검색 + 요약 | 코파일럿: "do(제재=강화)하면 분쟁 확률?" 같은 개입 쿼리 |
| 온톨로지: 연관 관계 (RELATES_TO) | 온톨로지: 인과 관계 (CAUSES, ENABLES, PREVENTS) 추가 |
| OSINT → 행위자 상태: 하드코딩 | OSINT 시그널에서 인과 요인 추출 → 행위자 상태 그라운딩 |

### 핵심 개념: 인과추론 3계층

Pearl의 인과 추론 사다리(Ladder of Causation)를 시스템에 적용한다:

```
Rung 3: 반사실 (Counterfactual)
  "제재를 하지 않았다면 분쟁이 일어났을까?"
  → DoWhy GCM counterfactual_samples()
  → What-If 비교에 인과 귀속 추가

Rung 2: 개입 (Intervention)
  "do(군사훈련=확대)하면 긴장도가 얼마나 오르는가?"
  → DoWhy GCM interventional_samples()
  → 코파일럿 개입 쿼리 API

Rung 1: 관찰 (Association)
  "군사훈련과 긴장도는 상관이 있는가?"
  → 시뮬레이션 로그에서 통계적 상관 분석
  → 현재 시스템이 이미 부분적으로 수행 (키워드 기반 긴장도)
```

---

## 2. V4 → V5 갭 분석

### 2.1 현재 데이터 흐름 (V4 — 인과추론 없음)

```
OSINT → 시드 → MiroFish 파이프라인 → 시뮬레이션 결과 (액션 로그)
                                                    ↓
                                     지정학 엔진 (규칙 기반 상태 전이)
                                                    ↓
                                     What-If (전체 재실행 → 키워드 긴장도 비교)
                                                    ↓
                                     브리핑 (LLM 서술적 내러티브)
```

**문제**: 각 단계에서 "왜"에 대한 답이 없다.
- 지정학 엔진: `threat_perception >= 0.6 → military_movement` 규칙은 있지만, "위협인식이 0.6이 된 원인"은 추적 불가
- What-If: `tension_advantage = -0.23` 이라는 숫자는 있지만, "그 -0.23 중 제재가 몇 %, 외교가 몇 %인지"는 답 불가
- 브리핑: LLM이 "A가 B를 야기했다"고 쓰지만, 통계적 근거 없음

### 2.2 V5 목표 데이터 흐름 (인과추론 통합)

```
OSINT → 시드 → MiroFish 파이프라인 → 시뮬레이션 결과 (액션 로그)
  ↓                                                    ↓
  ↓                                     ┌─────────────────────────┐
  ↓                                     │  Causal Intelligence    │
  ↓                                     │                         │
  ↓    ┌────────────────────────┐       │  ┌─ Causal DAG ───────┐ │
  └───→│ Causal Extractor       │──────→│  │ 도메인 지식 DAG     │ │
       │ (LLM 가설 + 통계 검증)  │       │  │ + 학습된 DAG       │ │
       └────────────────────────┘       │  │ + OSINT 추출 DAG   │ │
                                        │  └──────────┬──────────┘ │
              시뮬레이션 로그 ──────────→│  ┌──────────▼──────────┐ │
              (DataFrame 수집)          │  │ Causal Reasoner     │ │
                                        │  │ (DoWhy GCM)         │ │
                                        │  │  · 개입 쿼리        │ │
                                        │  │  · 반사실 추론      │ │
                                        │  │  · 인과 귀속        │ │
                                        │  └──────────┬──────────┘ │
                                        └─────────────┼───────────┘
                                                      ↓
                                   ┌──────────────────┼──────────────────┐
                                   ↓                  ↓                  ↓
                            What-If 인과 귀속    코파일럿 개입 쿼리   브리핑 인과 설명
```

### 2.3 발견된 6개 갭

| # | 갭 | 심각도 | V5 PRD |
|---|-----|--------|--------|
| 1 | 지정학 엔진의 규칙이 암묵적 — 공식 인과 DAG로 표현되지 않음 | Critical | PRD V8-1 |
| 2 | 시뮬레이션 로그가 인과 분석용 정형 데이터로 수집되지 않음 | Critical | PRD V8-1 |
| 3 | 개입(do) 쿼리와 반사실 추론 불가 | Critical | PRD V8-2 |
| 4 | What-If 비교에서 인과 귀속 없음 ("무엇이 차이를 만들었는가" 답 불가) | High | PRD V8-2 |
| 5 | OSINT 텍스트에서 인과 관계를 자동 추출하지 못함 | High | PRD V8-3 |
| 6 | 브리핑/코파일럿이 통계적 근거 없이 서술적 인과 기술만 수행 | High | PRD V8-3 |

---

## 3. V5 PRD 목록

### 실행 순서 및 의존성

```
PRD V8-1 (인과 DAG 기반)
  │
  └──→ PRD V8-2 (인과 추론 엔진)
          │
          └──→ PRD V8-3 (인과 내러티브)
```

V8-1은 DAG 정의 + 데이터 파이프라인으로 다른 모든 PRD의 기반.
V8-2는 DoWhy GCM 기반 추론 엔진으로 V8-1의 DAG와 데이터를 소비.
V8-3은 V8-2의 추론 결과를 OSINT 추출 및 사용자 대면 내러티브로 확장.

---

### PRD V8-1: 인과 DAG 기반 구축

**문제**: 지정학 엔진의 `PROPAGATION_RULES`/`CASCADE_RULES`는 인과 관계를 암묵적으로 인코딩하지만 공식 DAG로 표현되지 않았다. 시뮬레이션 로그는 인과 분석용 정형 데이터로 수집되지 않는다.

**솔루션**:
1. 기존 지정학 규칙을 NetworkX `DiGraph`로 공식화 (도메인 지식 DAG)
2. 시뮬레이션 로그를 라운드별 상태 변수 DataFrame으로 수집하는 파이프라인 구축
3. pgmpy 구조 학습으로 데이터 기반 DAG 발견 → 도메인 DAG와 비교/병합
4. 인과 DAG 저장소 (PostgreSQL + Neo4j 인과 엣지 확장)

**마일스톤**:
- M1: 도메인 지식 DAG 공식화 (PROPAGATION_RULES → NetworkX DiGraph)
- M2: 시뮬레이션 로그 수집 파이프라인 (액션/이벤트/상태 → DataFrame)
- M3: pgmpy 구조 학습 (HillClimb + BDeu) + 부트스트랩 검증
- M4: 인과 DAG 저장소 + API (CRUD, 시각화 데이터)

---

### PRD V8-2: 인과 추론 엔진

**문제**: 시뮬레이션에서 개입 쿼리("do(X)하면 Y가 어떻게 변하는가?")와 반사실 추론("X가 없었다면 Y가 어땠을까?")을 수행할 수 없다. What-If 비교에서 인과 귀속이 없다.

**솔루션**:
1. DoWhy GCM 기반 구조 인과 모형(SCM) 적합
2. 개입 쿼리 API (`interventional_samples`)
3. 반사실 쿼리 API (`counterfactual_samples`)
4. What-If 비교에 인과 귀속 추가 (어떤 이벤트가 tension_advantage의 N%를 설명)

**마일스톤**:
- M1: DoWhy GCM SCM 적합 + 개입 쿼리 서비스
- M2: 반사실 쿼리 서비스 + API 엔드포인트
- M3: What-If 인과 귀속 (`WhatIfComparison`에 `causal_attribution` 추가)
- M4: 코파일럿 인과 쿼리 통합

---

### PRD V8-3: 인과 내러티브 + LLM 하이브리드 추출

**문제**: OSINT 텍스트에서 인과 관계를 자동 추출하지 못한다. 브리핑/코파일럿이 통계적 근거 없이 서술적 인과 기술만 수행한다.

**솔루션**:
1. LLM 하이브리드 인과 추출 (LLM 가설 → 통계 검증, CauScientist 패턴)
2. 온톨로지에 인과 엣지 타입 추가 (CAUSES, ENABLES, PREVENTS)
3. 브리핑 생성에 인과 경로 기반 정량적 설명 주입
4. 코파일럿에 인과 DAG 경로 추적 기반 설명

**마일스톤**:
- M1: LLM 인과 가설 추출기 (구조화된 JSON 출력)
- M2: 통계 검증 파이프라인 (pgmpy + 부트스트랩)
- M3: 온톨로지 인과 엣지 타입 확장
- M4: 브리핑 + 코파일럿 인과 내러티브 통합

---

## 4. Tech Stack 변경

### 신규 의존성

| 패키지 | 용도 | V5 PRD |
|--------|------|--------|
| `dowhy` (v0.14+) | SCM 정의, 개입/반사실 쿼리, 인과 귀속 | PRD V8-2 |
| `pgmpy` (v1.0+) | 인과 구조 학습 (PC, HillClimb, BDeu) | PRD V8-1 |
| `econml` | 이질적 처치 효과 (CATE), 패널 데이터 DynamicDML | PRD V8-2 |
| `networkx` | 인과 DAG 그래프 정의 + 경로 추적 (DoWhy 의존성으로 이미 설치) | PRD V8-1 |

### 백엔드

| 변경 | V5 PRD |
|------|--------|
| `backend/app/causal/` 디렉토리 신규 | PRD V8-1, V8-2 |
| `backend/app/routers/causal.py` 신규 | PRD V8-2 |
| `backend/app/services/causal_extractor.py` 신규 | PRD V8-3 |
| `backend/app/services/causal_reasoner.py` 신규 | PRD V8-2 |
| `backend/app/services/causal_log_collector.py` 신규 | PRD V8-1 |
| `geopolitics/engine.py` 확장 (DAG 내보내기) | PRD V8-1 |
| `whatif_engine.py` 확장 (인과 귀속) | PRD V8-2 |
| `briefing_generator.py` 확장 (인과 설명) | PRD V8-3 |
| `copilot_context.py` 확장 (인과 쿼리) | PRD V8-3 |
| `database.py` 확장 (causal_models, causal_edges 테이블) | PRD V8-1 |

### 프론트엔드

| 변경 | V5 PRD |
|------|--------|
| `WhatIfCompareModal` 확장 (인과 귀속 섹션) | PRD V8-2 |
| 인과 DAG 시각화 (D3.js 방향 그래프) | PRD V8-1 |
| 코파일럿 인과 쿼리 UI | PRD V8-3 |

---

## 5. 성공 기준

V5 완료의 정의:

- [ ] 지정학 엔진의 규칙이 공식 인과 DAG로 표현되고 시각화 가능하다
- [ ] 시뮬레이션 로그가 인과 분석용 DataFrame으로 자동 수집된다
- [ ] 시뮬레이션 로그에서 인과 구조를 자동 학습하고 도메인 DAG와 비교할 수 있다
- [ ] `do(X=v)` 개입 쿼리로 "X를 v로 설정하면 Y가 어떻게 변하는가"에 정량적으로 답한다
- [ ] 반사실 쿼리로 "X가 없었다면 Y가 어땠을까"에 정량적으로 답한다
- [ ] What-If 비교에서 "tension_advantage의 N%는 이벤트 X가 설명"하는 인과 귀속이 제공된다
- [ ] OSINT 텍스트에서 인과 관계를 자동 추출하고 통계적으로 검증한다
- [ ] 브리핑 문서에 검증된 인과 경로 기반 정량적 설명이 포함된다

---

## 6. 우선순위 및 타임라인

| 주차 | PRD | 핵심 산출물 |
|------|-----|-----------|
| W1 | V8-1 M1-M2 | 도메인 DAG 공식화 + 시뮬레이션 로그 수집 파이프라인 |
| W2 | V8-1 M3-M4 | 구조 학습 + DAG 저장소 + API |
| W3 | V8-2 M1-M2 | DoWhy GCM 적합 + 개입/반사실 쿼리 서비스 + API |
| W4 | V8-2 M3-M4 | What-If 인과 귀속 + 코파일럿 인과 쿼리 |
| W5 | V8-3 M1-M2 | LLM 인과 추출 + 통계 검증 |
| W6 | V8-3 M3-M4 | 온톨로지 인과 엣지 + 브리핑/코파일럿 내러티브 |

---

## 7. Risks & Mitigations

| 리스크 | 심각도 | 완화 |
|--------|--------|------|
| DoWhy GCM 적합에 100+ 시뮬레이션 런 필요 | High | 시뮬레이션 자체가 데이터 생성기 — 축적 전까지 도메인 DAG만 사용. 최소 런 수 가드레일 추가 |
| DAG은 순환 불가 — 지정학 피드백 루프 표현 제한 | High | 시간 언롤링: `conflict_t0 → sanctions_t1 → conflict_t2`. AGENTS.md에 제약 명시 |
| LLM 단독 인과추론 F1=29% (Corr2Cause 벤치마크) | High | 반드시 통계 검증과 결합 (하이브리드 패턴). LLM은 가설 생성만, 검증은 pgmpy |
| OpenAI-compatible API의 structured output 지원 편차 | Medium | JSON 파싱 폴백 구현. `response_format` 미지원 시 프롬프트 기반 JSON 추출 |
| DoWhy/pgmpy 의존성 사이즈 (scipy, sklearn 등 전이 의존성) | Medium | Docker 이미지 별도 스테이지. 개발 환경에서는 optional dependency 그룹 |
| 인과 귀속 결과의 해석 오류 (비전문가 분석관) | Medium | UI에 해석 가이드 표시. "heuristic 추정치" 라벨 유지. 신뢰구간 필수 표시 |
| MiroFish 외부 서비스 코드 수정 제한 | Low | Gateway 레이어에서 인과 레이어 추가. MiroFish 무수정 가능 (로그 수집은 결과 파싱) |

---

## 8. 참고 문헌

| 자료 | 활용 |
|------|------|
| Pearl, "Causality" (2009) | 이론적 기반: SCM, do-calculus, 인과 사다리 |
| DoWhy GCM (PyWhy, v0.14, 2025) | 핵심 프레임워크: interventional/counterfactual_samples |
| pgmpy v1.0 (2025) | 구조 학습: PC, HillClimb, BDeu |
| CauScientist (arXiv:2601.13614, 2026) | LLM 하이브리드 인과 발견: 가설+검증 반복 패턴 |
| MAXS (arXiv:2601.09259, 2025) | 기존 What-If 비교 메트릭 (tension_advantage 등) |
| awslabs/causalif (Apache-2.0, 2025) | LLM prior + Hill Climb + BDeu 하이브리드 패턴 |
| GraphRAG-Causal (arXiv:2506.11600) | Neo4j + 인과 지식 그래프 아키텍처 |

---

## PRD 인덱스

| PRD | 설명 | 상태 |
|-----|------|------|
| [v5-full-osint-integration.md](prds/v5-full-osint-integration.md) | 전체 OSINT 피드 통합 + 상황 인식 패널 | Complete |
