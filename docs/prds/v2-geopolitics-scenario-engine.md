# PRD: 지정학 시나리오 엔진

> Status: Draft
> Created: 2026-03-20
> Dependencies: v2-oasis-platform-subclassing
> 관련 스펙: `specs/MVP-SPEC.md` Section 18 (Layer 4 SIMULATION), Section 19 (Critical 리스크 OASIS 커플링)
> 버전: v2.0

---

## 1. 문제 정의

OASIS는 소셜미디어 정보 전파 시뮬레이터다. "국가 행위자의 의사결정"과 "지정학 이벤트의 연쇄 반응"을 OASIS만으로 표현하면 메타포가 왜곡된다.

핵심 과제:
- OASIS는 "누가 무엇을 포스팅했는가"를 시뮬레이션하지, "국가가 왜 군사 이동을 결정했는가"를 시뮬레이션하지 않는다
- 국가 행위자의 목표, 제약, 의사결정 로직이 OASIS 내에 표현될 공간이 없다
- 지정학 이벤트(제재, 군사 이동)가 소셜 반응에 미치는 영향을 양방향으로 연결할 수 없다
- SPEC §18 Layer 4: OASIS를 "정보 전파 서브 시뮬레이터"로 한정하고 지정학 코어 엔진을 별도 구축

## 2. 솔루션 개요

- **상태 전이 모델** — 국가 행위자의 의사결정 상태 기계
- **행위자 목표/제약 프레임워크** — 각 행위자의 목표와 행동 제약 정의
- **지정학 이벤트 시스템** — 이벤트 생성, 전파, 결과 계산
- **OASIS 양방향 연동** — 지정학 결정 → 소셜 반응 → 여론 피드백 루프

## 3. 기술 상세

### 3.1 아키텍처 분리

```
지정학 코어 엔진 (신규)
    ↓ 지정학 결정 이벤트
OASIS GeopoliticsPlatform (서브클래스)
    ↓ 소셜 반응 + 여론 피드백
지정학 코어 엔진 (상태 업데이트)
```

### 3.2 행위자 상태 모델

행위자 상태 필드: `threat_perception` (0~1), `domestic_pressure` (0~1), `resource_level` (0~1), `objectives[]`, `constraints[]`, `active_actions[]`

의사결정 흐름: 위협 인식 업데이트 → 목표 달성 가능성 평가 → 제약 조건 필터링 → 최적 행동 선택 (규칙 기반, LLM은 선택적)

### 3.3 이벤트 전파 규칙

- 군사 이동 → 인접국 `threat_perception` 상승
- 제재 발동 → 대상국 `resource_level` 감소 + `domestic_pressure` 상승
- 외교 성명 → 관련국 여론 변화 (OASIS 트리거)

### 3.4 OASIS 양방향 연동

```python
class GeopoliticsOASISBridge:
    async def geopolitics_to_social(self, event: GeopoliticsEvent):
        social_prompt = self._build_social_prompt(event)
        await self.oasis_platform.inject_event(social_prompt)

    async def social_to_geopolitics(self, sentiment: SentimentData):
        for actor_id, pressure_delta in sentiment.by_country.items():
            await self.engine.update_domestic_pressure(actor_id, pressure_delta)
```

### 3.5 수정 대상 파일

```
backend/app/geopolitics/
├── engine.py        # 신규: DecisionEngine, 상태 전이
├── actors.py        # 신규: GeopoliticalActorState, 목표/제약
├── events.py        # 신규: GeopoliticsEvent, 전파 규칙
├── oasis_bridge.py  # 신규: OASIS 양방향 연동
└── router.py        # 신규: 지정학 엔진 API
```

## 4. 마일스톤

- [x] **M1: 행위자 상태 모델** — GeopoliticalActorState, 목표/제약 프레임워크
  - 검증: 행위자 상태 생성 + 직렬화/역직렬화 확인

- [x] **M2: 상태 전이 엔진** — DecisionEngine, 규칙 기반 의사결정 (LLM 없이)
  - 검증: 위협 인식 상승 → 군사 이동 결정 트리거 확인

- [x] **M3: 지정학 이벤트 시스템** — 이벤트 생성, 전파, 영향 계산
  - 검증: 제재 이벤트 → 대상국 자원 감소 + 인접국 상태 변화 확인

- [ ] **M4: OASIS 양방향 연동** — GeopoliticsOASISBridge, 피드백 루프
  - 검증: 군사 이동 → OASIS 소셜 반응 → 여론 피드백 → 행위자 상태 업데이트

## 5. 성공 기준

- 국가 행위자가 목표와 제약에 따라 자율적으로 행동을 결정한다
- 지정학 이벤트가 다른 행위자의 상태에 연쇄적으로 영향을 준다
- OASIS 소셜 시뮬레이션과 지정학 엔진이 양방향으로 연동된다
- 시뮬레이션 결과에서 지정학 이벤트 타임라인을 추출할 수 있다

## 6. 위험 및 완화

| 위험 | 완화 |
|------|------|
| 상태 전이 규칙이 너무 단순해 현실적이지 않은 결과 | 초기에는 규칙 기반으로 구현. LLM 기반 의사결정은 M2 이후 점진적 도입 |
| OASIS 피드백 루프가 발산 (여론 → 행동 → 여론 무한 증폭) | 피드백 감쇠 계수 적용. 시뮬레이션 스텝당 최대 영향 크기 제한 |
| 지정학 엔진과 OASIS 동기화 타이밍 문제 | 이벤트 큐 기반 비동기 연동. 순서 보장 메커니즘 |

## 7. 참고

### 관련 PRD
- **v2-oasis-platform-subclassing** — GeopoliticsPlatform 서브클래스 기반
- **v2-action-layer** — 지정학 결정을 Action으로 기록
- **v2-snapshot-branching** — 지정학 시뮬레이션 격리

### SPEC 근거
- §18 Layer 4 SIMULATION: OASIS를 서브 시뮬레이터로 한정, 지정학 코어 엔진 별도 구축
- §19 Critical 리스크: OASIS 커플링이 지정학 표현력의 근본적 한계

## 진행 로그

| 날짜 | 상태 | 내용 |
|------|------|------|
| 2026-03-20 | Draft | v2 지정학 시나리오 엔진 PRD 초안 작성 |
| 2026-03-21 | M1-M2 완료 | GeopoliticalActorState(목표/제약/상태) + DecisionEngine(규칙 기반 의사결정) + GeopoliticsEvent(전파 규칙). M3-M4는 OASIS 서브클래싱 의존 |
| 2026-03-21 | M3 완료 | CASCADE_RULES(연쇄 이벤트), apply_event_with_cascade(재귀+감쇠), run_simulation(N라운드). M4만 OASIS 런타임 의존 |
