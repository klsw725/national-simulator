# PRD: OASIS Platform 서브클래싱

> Status: Draft
> Created: 2026-03-20
> Dependencies: 없음 (독립적)
> 관련 스펙: `specs/MVP-SPEC.md` Section 17.3 (OASIS 확장성 분석), Section 19 (Critical 리스크)
> 버전: v2.0

---

## 1. 문제 정의

MVP는 OASIS의 소셜미디어 메타포(트위터/레딧 스타일)를 그대로 사용한다. "정보 전파" 시뮬레이션에는 적합하지만, 지정학 행동(외교 성명, 군사 이동, 제재)을 직접 모델링하기에는 부적합하다.

핵심 과제:
- OASIS ActionType이 소셜미디어 행동(post, like, follow)에 고정되어 있다
- 지정학 행위자(국가, 군사 조직)를 UserInfo로 표현하면 의미가 왜곡된다
- 커스텀 플랫폼 없이는 지정학 이벤트를 OASIS 시뮬레이션에 주입할 수 없다
- SPEC §17.3: OASIS 소스 ~20줄 수정으로 서브클래싱 가능 (Critical 리스크 완화)

## 2. 솔루션 개요

- **ActionType enum 확장** — 지정학 행동 타입 추가 (외교/군사/경제)
- **GeopoliticsPlatform 서브클래스** — OASIS BasePlatform 상속, 지정학 전용 로직
- **커스텀 UserInfo 템플릿** — 국가/조직 행위자 프로필 구조
- **database.py 테이블 추가** — 지정학 이벤트 저장 (~10줄)

## 3. 기술 상세

### 3.1 ActionType 확장 (MiroFish 내 ~20줄 수정)

```python
from oasis.social.actions import ActionType

class GeopoliticsActionType(ActionType):
    DIPLOMATIC_STATEMENT = "diplomatic_statement"
    TREATY_SIGN = "treaty_sign"
    MILITARY_MOVEMENT = "military_movement"
    MILITARY_EXERCISE = "military_exercise"
    SANCTION_IMPOSE = "sanction_impose"
    TRADE_RESTRICTION = "trade_restriction"
```

### 3.2 GeopoliticsPlatform 서브클래스

```python
from oasis.social.platform import BasePlatform

class GeopoliticsPlatform(BasePlatform):
    async def handle_action(self, actor_id, action_type, payload):
        if action_type in GeopoliticsActionType.__members__:
            return await self._handle_geopolitics_action(actor_id, action_type, payload)
        return await super().handle_action(actor_id, action_type, payload)
```

### 3.3 커스텀 UserInfo 템플릿

국가 행위자 프로필 필드: `actor_type` (state/non_state/igo), `country_code`, `military_capability` (0~1), `economic_power` (0~1), `diplomatic_influence` (0~1), `alliances[]`, `adversaries[]`

### 3.4 수정 대상 파일

> **주의**: SPEC §17.3에서 명시적으로 허용한 MiroFish 내부 확장 포인트만 수정.

```
mirofish-ko/src/
├── platforms/geopolitics_platform.py   # 신규: GeopoliticsPlatform
├── actions/geopolitics_actions.py      # 신규: GeopoliticsActionType
└── database.py                         # 수정: geopolitics_events 테이블 추가
```

## 4. 마일스톤

- [ ] **M1: ActionType 확장** — GeopoliticsActionType enum, 기존 OASIS 타입과 호환
  - 검증: 기존 OASIS 시뮬레이션 regression 없음

- [ ] **M2: GeopoliticsPlatform** — BasePlatform 서브클래스, 지정학 액션 핸들러
  - 검증: DIPLOMATIC_STATEMENT 액션 → geopolitics_events 저장 확인

- [ ] **M3: 커스텀 UserInfo + DB 테이블** — 국가 행위자 프로필, geopolitics_events 테이블
  - 검증: 시드 생성 시 국가 행위자 프로필 포함 확인

- [ ] **M4: 통합 테스트** — GeopoliticsPlatform으로 전체 시뮬레이션 실행
  - 검증: 지정학 이벤트 포함 시뮬레이션 결과 생성

## 5. 성공 기준

- 지정학 행동(외교/군사/경제)이 OASIS 시뮬레이션에서 직접 실행된다
- 기존 소셜미디어 시뮬레이션 기능이 regression 없이 동작한다
- 국가 행위자 프로필이 소셜미디어 사용자와 구분되어 표현된다
- MiroFish 소스 수정이 ~20줄 이내로 제한된다

## 6. 위험 및 완화

| 위험 | 완화 |
|------|------|
| OASIS 업스트림 업데이트 시 서브클래스 호환성 깨짐 | OASIS 버전 고정. 업스트림 변경 시 서브클래스 검토 |
| 지정학 행동이 OASIS 내부 상태와 충돌 | 지정학 이벤트는 별도 테이블에 저장. OASIS 내부 상태 최소 수정 |
| MiroFish 소스 수정 범위 확대 위험 | 수정 범위를 ~20줄로 엄격히 제한. 추가 수정 필요 시 PRD 업데이트 |

## 7. 참고

### 관련 PRD
- **v2-geopolitics-scenario-engine** — 이 서브클래싱을 기반으로 지정학 코어 엔진 구축

### SPEC 근거
- §17.3: OASIS 확장성 분석 — 서브클래싱으로 소셜미디어 메타포 탈피 가능
- §19 Critical 리스크: OASIS 커플링이 지정학 시뮬레이션의 표현력을 제한

## 진행 로그

| 날짜 | 상태 | 내용 |
|------|------|------|
| 2026-03-20 | Draft | v2 OASIS Platform 서브클래싱 PRD 초안 작성 |
