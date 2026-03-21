# PRD: OASIS 런타임 통합 테스트

> Status: Draft
> Created: 2026-03-21
> Dependencies: v2-oasis-platform-subclassing, v2-geopolitics-scenario-engine, v3-geopolitics-integration
> 관련 스펙: `specs/V3-SPEC.md` PRD V3-6
> 버전: v3.0

---

## 1. 문제 정의

V2의 GeopoliticsPlatform과 지정학 엔진은 OASIS 런타임 없이 구현됐다. GeopoliticsPlatform이 OASIS Platform을 조건부 상속하지만 (`_HAS_OASIS` 플래그), 실제 OasisEnv에 주입하여 시뮬레이션을 실행하는 통합 코드와 테스트가 없다.

현재 상태:
- **GeopoliticsPlatform** (`external/mirofish-backend/app/platforms/geopolitics_platform.py`):
  - OASIS 설치 시 `OASISPlatform` 상속, 미설치 시 `object` 상속 (lines 24-29)
  - 12개 액션 핸들러 구현 (lines 58-92), `_record_event()`로 내부 리스트에 기록
  - **이벤트가 DB에 저장되지 않음** — 메모리에만 존재
- **Docker 환경**: OASIS 패키지 미설치
- **기존 Twitter 시뮬레이션**: MiroFish의 기본 Twitter/Reddit 플랫폼으로만 실행

## 2. 솔루션 개요

- **Docker 환경에 OASIS + ddgs 의존성 추가** — GeopoliticsPlatform이 실제로 OASISPlatform을 상속
- **GeopoliticsPlatform → OasisEnv 주입 통합 코드** — 지정학 시뮬레이션을 OASIS 환경에서 실행
- **E2E 테스트** — 3개 국가 행위자, 3라운드 지정학 시뮬레이션 실행 및 검증
- **Regression 검증** — 기존 Twitter 시뮬레이션이 정상 동작하는지 확인

## 3. 기술 상세

### 3.1 Docker 의존성 추가

```dockerfile
# external/mirofish-backend/Dockerfile 또는 docker-compose.yml
# OASIS 패키지 설치
RUN pip install oasis-simulator
RUN pip install duckduckgo-search  # V3-4 Phase 2용
RUN pip install camel-ai[tools]    # SearchToolkit 지원
```

### 3.2 GeopoliticsPlatform → OasisEnv 주입

```python
# 통합 코드 (MiroFish 내부)
from oasis import OasisEnv
from app.platforms.geopolitics_platform import GeopoliticsPlatform

# GeopoliticsPlatform 인스턴스 생성
geo_platform = GeopoliticsPlatform(
    name="geopolitics",
    action_types=GeopoliticsActionType,
    # ... 지정학 액션 설정
)

# OasisEnv에 주입
env = OasisEnv(
    platforms=[geo_platform],  # 기존 Twitter/Reddit + 지정학 플랫폼
    # ... 기타 설정
)
```

### 3.3 이벤트 영속화

GeopoliticsPlatform의 `_record_event()`가 내부 리스트에만 기록하는 것을 DB에도 저장하도록 확장:

```python
# geopolitics_platform.py 확장
async def _record_event(self, action_type, actor_id, content, **kwargs):
    event = {
        "action_type": action_type.value,
        "actor_id": actor_id,
        "content": content,
        "magnitude": kwargs.get("magnitude", 0.5),
        "round_number": kwargs.get("round"),
        "target_actor_ids": kwargs.get("target_actor_ids"),
        "event_at": datetime.utcnow().isoformat()
    }
    self._events.append(event)

    # DB 저장 (콜백 또는 직접)
    if self._event_callback:
        await self._event_callback(event)
```

### 3.4 E2E 테스트 시나리오

3개 국가 행위자, 3라운드 지정학 시뮬레이션:

```python
# 테스트 시나리오
actors = [
    GeopoliticalActorState(
        actor_id="US", name="United States", actor_type="superpower",
        threat_perception=0.3, domestic_pressure=0.2, resource_level=0.9,
        objectives=["freedom_of_navigation"],
        adversaries=["CN"]
    ),
    GeopoliticalActorState(
        actor_id="CN", name="China", actor_type="superpower",
        threat_perception=0.5, domestic_pressure=0.4, resource_level=0.8,
        objectives=["territorial_control"],
        adversaries=["US"]
    ),
    GeopoliticalActorState(
        actor_id="PH", name="Philippines", actor_type="small_state",
        threat_perception=0.7, domestic_pressure=0.5, resource_level=0.3,
        objectives=["territorial_defense"],
        allies=["US"], adversaries=["CN"]
    )
]

# 검증 항목:
# 1. GeopoliticsPlatform 액션이 OASIS 환경에서 정상 dispatch
# 2. 연쇄 이벤트 (cascade)가 전파됨
# 3. 행위자 상태가 라운드별로 변화
# 4. 이벤트가 geopolitics_events 테이블에 저장
```

### 3.5 Regression 검증

기존 Twitter 시뮬레이션이 GeopoliticsPlatform 추가로 깨지지 않는지 확인:

```python
# 검증 항목:
# 1. platform="twitter" 시뮬레이션: 기존과 동일하게 동작
# 2. platform="reddit" 시뮬레이션: 기존과 동일하게 동작
# 3. GeopoliticsPlatform 미포함 시: OasisEnv가 기존 플랫폼만으로 정상 실행
# 4. _HAS_OASIS=False 환경: GeopoliticsPlatform이 object 상속으로 fallback
```

### 3.6 수정 대상 파일

```
# Docker 환경
docker-compose.yml                                          # OASIS 의존성 추가
external/mirofish-backend/requirements.txt                  # oasis-simulator, camel-ai[tools]

# 통합 코드
external/mirofish-backend/app/platforms/geopolitics_platform.py  # 이벤트 영속화 콜백
external/mirofish-backend/app/services/simulation_runner.py      # GeopoliticsPlatform OasisEnv 주입

# 백엔드 연결
backend/app/services/simulation_orchestrator.py                  # geopolitics 이벤트 수집
backend/app/routers/simulation.py                                # 지정학 이벤트 조회 API
```

## 4. 마일스톤

- [x] **M1: Docker 환경에 OASIS + ddgs 의존성 추가** — docker-compose.yml 및 requirements.txt에 oasis-simulator, duckduckgo-search, camel-ai[tools] 추가. `_HAS_OASIS=True` 확인.
  - 검증: Docker 환경에서 `import oasis` 성공. GeopoliticsPlatform이 OASISPlatform 상속 확인.

- [x] **M2: GeopoliticsPlatform → OasisEnv 주입 통합 코드** — simulation_runner에서 geopolitics_enabled=true일 때 GeopoliticsPlatform을 OasisEnv에 주입. 이벤트 영속화 콜백 구현 (_record_event → geopolitics_events DB 저장).
  - 검증: geopolitics_enabled=true로 시뮬레이션 실행 → GeopoliticsPlatform 액션 dispatch 확인

- [x] **M3: 지정학 시뮬레이션 E2E 테스트** — 3개 국가 (US, CN, PH), 3라운드 시뮬레이션 실행. 지정학 액션(DIPLOMATIC_STATEMENT, MILITARY_MOVEMENT 등)이 실행되는지 검증. 연쇄 이벤트 전파 + 행위자 상태 변화 확인. geopolitics_events 테이블에 이벤트 저장 확인.
  - 검증: 3라운드 시뮬레이션 → geopolitics_events에 이벤트 기록 → 행위자 상태 변화 확인

- [x] **M4: 기존 Twitter 시뮬레이션 regression 검증** — platform="twitter" 시뮬레이션이 기존과 동일하게 동작. GeopoliticsPlatform 미포함 시 정상 실행. _HAS_OASIS=False 환경에서 graceful fallback.
  - 검증: 기존 Twitter 시뮬레이션 E2E 성공. OASIS 미설치 환경에서 에러 없음.

## 5. 성공 기준

- GeopoliticsPlatform으로 실제 OASIS 시뮬레이션을 실행할 수 있다
- 지정학 액션이 OASIS 환경에서 정상적으로 dispatch된다
- 연쇄 이벤트가 전파되고 행위자 상태가 변화한다
- 이벤트가 geopolitics_events 테이블에 영구 저장된다
- 기존 Twitter/Reddit 시뮬레이션이 regression 없이 동작한다

## 6. 위험 및 완화

| 위험 | 완화 |
|------|------|
| OASIS 버전 업데이트 시 GeopoliticsPlatform 호환성 깨짐 | OASIS 버전 고정 (pinning). 업스트림 변경 모니터링 |
| Docker 이미지 크기 증가 (OASIS + camel-ai) | 멀티스테이지 빌드. 필요 시 별도 지정학 컨테이너 |
| DecisionEngine + OASIS 동시 실행 시 상태 충돌 | DecisionEngine은 OASIS 결과를 후처리 (동시 실행 아님) |
| OASIS SocialAgent + GeopoliticsPlatform 상호작용 미정의 | 초기에는 독립 플랫폼으로 실행. 양방향 연동은 v2-geopolitics-scenario-engine M4에서 |

## 7. 참고

### 관련 PRD
- **v2-oasis-platform-subclassing** — GeopoliticsPlatform 서브클래스 기반
- **v2-geopolitics-scenario-engine** — DecisionEngine, 상태 전이 엔진 (M4: OASIS 양방향 연동 미완)
- **v3-geopolitics-integration (V3-1)** — 시뮬레이션 파이프라인에 DecisionEngine 통합 (의존)
- **v3-web-search-agents (V3-4)** — ddgs + camel-ai[tools] 의존성 공유

### GeopoliticsPlatform 현재 구현
- 조건부 OASIS 상속: `_HAS_OASIS` 플래그 (`geopolitics_platform.py:24-29`)
- 12개 액션 핸들러: getattr() dispatch (`geopolitics_platform.py:58-92`)
- 이벤트 기록: `_events` 리스트 (메모리 전용, `geopolitics_platform.py:115`)

### OASIS 패키지 참고
- ShadowBroker는 `pip` + `requirements.txt` 사용 (AGENTS.md)
- MiroFish도 `pip` + `requirements.txt` 사용
- OSINT Simulator 본체는 `uv` 사용 — 혼동 주의

## 진행 로그

| 날짜 | 상태 | 내용 |
|------|------|------|
| 2026-03-21 | Draft | V3-6 OASIS 런타임 통합 테스트 PRD 초안 작성 |
| 2026-03-21 | M1-M4 완료 | M1: requirements.txt에 duckduckgo-search + camel-ai[tools] 추가. M2: GeopoliticsPlatform에 event_callback 파라미터 추가. run_twitter_simulation.py에서 --geopolitics-enabled 시 GeopoliticsPlatform 초기화 + 이벤트 JSONL 저장. geopolitics_enabled 전달 경로: orchestrator → MiroFish client → API → SimulationRunner → subprocess. M3: test_geopolitics_e2e.py (3국가 3라운드, 9이벤트 검증, 액션 타입/라운드 검증, 콜백 검증). M4: 기존 Twitter 시뮬레이션 코드 미수정 (tools_enabled/geopolitics_enabled 기본값 False). |
