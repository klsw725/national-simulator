# PRD: 인터랙티브 지정학 — 듀얼 모드

> Status: Draft
> Created: 2026-03-30
> Dependencies: v4-interactive-simulation, v2-geopolitics-scenario-engine, v4-ai-guided-decisions
> 관련 스펙: V4-SPEC.md (DecisionPoint), V5-SPEC.md (지정학 엔진)
> 버전: v9.1

---

## 1. 문제 정의

지정학 분석은 시뮬레이션 완료 후 일괄 실행(post-hoc)되며 분석관이 개입할 수 없다. `DecisionEngine.run_simulation(rounds=3)`가 3라운드를 한 번에 돌리고 결과만 DB에 저장한다. 분석관은 "만약 중국의 군사 이동에 외교적으로 대응했다면?"이라는 질문에 답할 수 없고, 시나리오 방향을 실시간으로 조정할 수도 없다.

### 현황

| 역량 | 현재 상태 | 필요 |
|------|----------|------|
| 지정학 실행 | 3라운드 일괄, `engine.run_simulation(rounds=3)` | 라운드 단위 실행 + 중간 정지 |
| 분석관 개입 | ❌ 없음 | 이벤트별 행동 선택 또는 시나리오 방향 결정 |
| 행동 결정 | 규칙 기반 자동 (`_decide_single`) | 특정 actor 행동을 사용자가 오버라이드 |
| 상태 조정 | ❌ 없음 | 시나리오 방향에 따라 전체 actor state 일괄 조정 |
| DecisionPoint 연동 | seed_selection, parameter_recommendation만 | 지정학 이벤트 대응 + 시나리오 방향 타입 추가 |

### 제약 조건

- **MiroFish 무수정**: MiroFish 시뮬레이션은 이미 완료된 상태에서 지정학 분석이 시작된다. MiroFish 라운드와 인터리빙하지 않는다.
- **엔진 규칙 무변경**: `PROPAGATION_RULES`, `CASCADE_RULES`, `_decide_single` 규칙 자체는 수정하지 않는다. 사용자 선택은 actor state 또는 행동을 오버라이드하는 방식으로 반영한다.
- **기존 auto 모드 유지**: `geopolitics_mode: "auto"`는 현재 동작(일괄 3라운드)을 그대로 유지한다. 하위 호환성 보장.
- **일시정지 최대 시간**: 30분. 초과 시 자동으로 현재 상태 기준 나머지 라운드 자동 진행.

---

## 2. 솔루션 개요

### 듀얼 모드 인터랙티브 지정학

시뮬레이션 시작 시 분석관이 지정학 모드를 선택한다:

| 모드 | 역할 | 일시정지 조건 | 선택 대상 |
|------|------|-------------|----------|
| `auto` | 기존 동작 | 없음 | 없음 |
| `actor_role` | 특정 국가 역할 수행 | 내 국가 관련 고긴장 이벤트 | 해당 국가의 다음 행동 |
| `game_master` | 시나리오 방향 결정 | 전체 고긴장 이벤트 또는 cascade 발생 | 다음 라운드 전체 방향 |

### 흐름

```
MiroFish 시뮬레이션 완료
    ↓
_step_geopolitics_interactive()
    ↓
라운드 1 실행 (run_single_round)
    ↓
should_pause() 판정
    ├─ No → 라운드 2 자동 진행
    └─ Yes ↓
         DecisionPoint 생성 (모드별 타입 분기)
         status = "simulating:geopolitics_paused"
         [사용자 선택 대기]
              ↓
         resolve → 선택 반영
              ↓
         라운드 2 실행 (수정된 상태)
              ↓
         ... 반복 ... → 완료
```

### 핵심 설계 결정

| 결정 | 선택 | 근거 |
|------|------|------|
| 실행 단위 | 라운드 1개씩 | 기존 `run_simulation(rounds=N)` 루프를 분리. 최소 변경 |
| 일시정지 메커니즘 | DecisionPoint + 상태 플래그 | 기존 `checkpoint:decision` 패턴 재활용. 신규 인프라 불필요 |
| Actor Role 반영 | `override_next_action(actor_id, action)` | `_decide_single()` 수정 없이 1회성 오버라이드 |
| Game Master 반영 | actor state delta 일괄 적용 | 엔진 규칙은 그대로, 입력 state만 변경 |
| 일시정지 조건 | magnitude ≥ 임계치 또는 cascade 발생 | 매 라운드 정지하면 피로. 의미 있는 이벤트에서만 |
| 지정학 라운드 수 | 기존 3라운드 유지, 설정 가능 | `geopolitics_rounds` 파라미터로 조정 가능 |
| 선택지 생성 | 규칙 기반 (LLM 불필요) | 가능한 행동은 6종 고정. 각 행동의 예상 효과를 PROPAGATION_RULES에서 계산 |

---

## 3. 기술 상세

### 3.1 SimulationParams 확장

```python
# backend/app/models/scenario.py — SimulationParams에 추가

class GeopoliticsMode(str, Enum):
    AUTO = "auto"                  # 기존 동작: 3라운드 일괄
    ACTOR_ROLE = "actor_role"      # 특정 국가 역할
    GAME_MASTER = "game_master"    # 시나리오 방향 결정

class SimulationParams(BaseModel):
    # ... 기존 필드 ...
    geopolitics_enabled: bool = True
    geopolitics_mode: GeopoliticsMode = GeopoliticsMode.AUTO
    geopolitics_player_actor_id: str | None = None   # actor_role 모드 전용
    geopolitics_rounds: int = 3
    geopolitics_pause_threshold: float = 0.5         # 일시정지 magnitude 임계치
```

### 3.2 DecisionPointType 확장

```python
# backend/app/models/decision_point.py

class DecisionPointType(str, Enum):
    SEED_SELECTION = "seed_selection"
    ACTOR_CONFIGURATION = "actor_configuration"
    PARAMETER_RECOMMENDATION = "parameter_recommendation"
    GEOPOLITICS_ACTOR_RESPONSE = "geopolitics_actor_response"  # 신규
    GEOPOLITICS_DIRECTION = "geopolitics_direction"             # 신규
```

### 3.3 지정학 일시정지 상태 저장

```sql
-- 기존 simulation_results 테이블의 status 값 확장
-- 신규 상태: 'simulating:geopolitics_paused'

-- 지정학 엔진 스냅샷 (라운드 간 상태 보존)
CREATE TABLE IF NOT EXISTS geopolitics_snapshots (
    id TEXT PRIMARY KEY,
    scenario_id TEXT NOT NULL REFERENCES scenarios(id),
    result_id TEXT NOT NULL,
    round_number INTEGER NOT NULL,
    engine_state TEXT NOT NULL,           -- JSON: 전체 actor 상태 + 이벤트 로그
    pending_decision_point_id TEXT,       -- 현재 대기 중인 DecisionPoint
    geopolitics_mode TEXT NOT NULL,       -- 'actor_role' | 'game_master'
    player_actor_id TEXT,                 -- actor_role일 때만
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_geo_snap_scenario ON geopolitics_snapshots(scenario_id);
CREATE INDEX IF NOT EXISTS idx_geo_snap_result ON geopolitics_snapshots(result_id);
```

### 3.4 DecisionEngine 확장

```python
# backend/app/geopolitics/engine.py — 기존 클래스에 메서드 추가

class DecisionEngine:
    # ... 기존 코드 ...

    def __init__(self):
        # ... 기존 ...
        self._action_overrides: dict[str, str] = {}  # actor_id → action

    def override_next_action(self, actor_id: str, action: str) -> None:
        """다음 라운드에서 특정 actor의 행동을 오버라이드. 1회성."""
        self._action_overrides[actor_id] = action

    def apply_direction_deltas(self, deltas: dict[str, float],
                                applies_to: str = "all") -> None:
        """Game Master 선택에 따라 전체/적대/동맹 actor의 state를 일괄 조정."""
        for actor in self._actors.values():
            if applies_to == "adversaries" and not self._is_adversary(actor):
                continue
            if applies_to == "allies" and not self._is_ally(actor):
                continue
            for field, delta in deltas.items():
                current = getattr(actor, field, None)
                if current is not None:
                    setattr(actor, field, current + delta)
            actor.clamp_state()

    def run_single_round(self) -> dict:
        """기존 run_round()를 외부에서 호출 가능하게 래핑.
        오버라이드가 있으면 _decide_single 대신 적용."""
        round_result = self._execute_round_with_overrides()
        self._action_overrides.clear()  # 1회성: 사용 후 초기화
        return round_result

    def _execute_round_with_overrides(self) -> dict:
        """run_round() 변형. 오버라이드된 actor는 규칙 대신 지정 행동 사용."""
        actions = {}
        for actor_id, actor in self._actors.items():
            if actor_id in self._action_overrides:
                actions[actor_id] = self._action_overrides[actor_id]
            else:
                actions[actor_id] = self._decide_single(actor)
        # ... 이벤트 생성 + 적용 + cascade (기존 로직) ...
        return round_result

    def serialize_state(self) -> dict:
        """엔진 전체 상태를 직렬화 (스냅샷 저장용)."""
        return {
            "actors": {aid: actor.model_dump() for aid, actor in self._actors.items()},
            "event_log": self._event_log,
            "round": self._round,
        }

    @classmethod
    def from_state(cls, state: dict) -> "DecisionEngine":
        """직렬화된 상태에서 엔진 복원."""
        engine = cls()
        for aid, actor_data in state["actors"].items():
            engine.add_actor(GeopoliticalActorState(**actor_data))
        engine._event_log = state["event_log"]
        engine._round = state["round"]
        return engine
```

### 3.5 일시정지 판정 로직

```python
# backend/app/services/geopolitics_interactive.py (신규)

def should_pause(
    round_result: dict,
    mode: GeopoliticsMode,
    player_actor_id: str | None,
    threshold: float = 0.5,
) -> bool:
    if mode == GeopoliticsMode.AUTO:
        return False

    events = round_result.get("events", []) + round_result.get("cascade_events", [])

    if mode == GeopoliticsMode.ACTOR_ROLE:
        for event in events:
            involves_player = (
                event.get("source_actor_id") == player_actor_id
                or player_actor_id in event.get("target_actor_ids", [])
            )
            if involves_player and event.get("magnitude", 0) >= threshold:
                return True
        return False

    elif mode == GeopoliticsMode.GAME_MASTER:
        if round_result.get("cascade_events"):
            return True
        for event in events:
            if event.get("magnitude", 0) >= threshold:
                return True
        return False

    return False
```

### 3.6 선택지 생성

```python
# backend/app/services/geopolitics_interactive.py (계속)

POSSIBLE_ACTIONS = [
    "military_movement", "military_exercise", "sanction_impose",
    "trade_restriction", "diplomatic_statement", "treaty_sign", "do_nothing",
]

ACTION_LABELS = {
    "military_movement":   "군사 대응",
    "military_exercise":   "군사 훈련",
    "sanction_impose":     "경제 제재",
    "trade_restriction":   "무역 제한",
    "diplomatic_statement": "외교 성명",
    "treaty_sign":         "조약 제안",
    "do_nothing":          "관망",
}

ACTION_DESCRIPTIONS = {
    "military_movement":   "상대 위협에 동등 수준 군사력으로 대응합니다.",
    "military_exercise":   "군사 훈련으로 억지력을 과시하되 직접 대치는 피합니다.",
    "sanction_impose":     "경제 제재를 부과하여 상대 자원을 압박합니다.",
    "trade_restriction":   "무역 제한으로 경제적 압박을 가합니다.",
    "diplomatic_statement": "공개 성명으로 입장을 표명하고 외교 채널을 활용합니다.",
    "treaty_sign":         "동맹국과의 협력을 강화하고 긴장 완화를 시도합니다.",
    "do_nothing":          "현 상황을 유지하며 추가 정보를 수집합니다.",
}

DIRECTION_OPTIONS = [
    {
        "id": "escalate",
        "label": "긴장 고조",
        "description": "군사적 대치 심화. 충돌 가능성을 탐색합니다.",
        "deltas": {"threat_perception": +0.10},
        "applies_to": "all",
    },
    {
        "id": "diplomatic",
        "label": "외교적 전환",
        "description": "외교 채널로 전환. 긴장 완화를 시도합니다.",
        "deltas": {"threat_perception": -0.10, "domestic_pressure": +0.05},
        "applies_to": "all",
    },
    {
        "id": "economic",
        "label": "경제전 전환",
        "description": "경제적 수단으로 압박을 전환합니다.",
        "deltas": {"resource_level": -0.15},
        "applies_to": "adversaries",
    },
    {
        "id": "maintain",
        "label": "현상 유지",
        "description": "현재 역학 관계를 유지하고 엔진 규칙대로 진행합니다.",
        "deltas": {},
        "applies_to": "all",
    },
]


def build_actor_response_options(
    engine: DecisionEngine,
    actor_id: str,
    trigger_event: dict,
) -> list[dict]:
    """Actor Role 모드: 가능한 행동별 예상 영향을 계산하여 옵션 리스트 생성."""
    from app.geopolitics.events import PROPAGATION_RULES

    actor = engine.get_actor(actor_id)
    engine_recommendation = engine._decide_single(actor)

    options = []
    for action in POSSIBLE_ACTIONS:
        predicted_deltas = PROPAGATION_RULES.get(action, {})
        option = {
            "id": action,
            "label": ACTION_LABELS[action],
            "description": ACTION_DESCRIPTIONS[action],
            "confidence": 0.0,
            "reasoning": "",
            "data": {
                "action": action,
                "predicted_deltas": predicted_deltas,
                "engine_recommended": action == engine_recommendation,
            },
        }
        if action == engine_recommendation:
            option["confidence"] = 0.85
            option["reasoning"] = f"엔진 규칙 기반 추천 (threat={actor.threat_perception:.2f}, pressure={actor.domestic_pressure:.2f}, resource={actor.resource_level:.2f})"
        options.append(option)

    return options


def build_direction_options(round_result: dict) -> list[dict]:
    """Game Master 모드: 시나리오 방향 옵션 리스트 생성."""
    options = []
    for direction in DIRECTION_OPTIONS:
        options.append({
            "id": direction["id"],
            "label": direction["label"],
            "description": direction["description"],
            "confidence": 0.0,
            "reasoning": "",
            "data": {
                "direction": direction["id"],
                "state_deltas": direction["deltas"],
                "applies_to": direction["applies_to"],
            },
        })
    return options
```

### 3.7 Orchestrator 통합

```python
# backend/app/services/simulation_orchestrator.py — 기존 _step_geopolitics_analysis 옆에 추가

async def _step_geopolitics_interactive(
    self,
    scenario_id: str,
    result_id: str,
    actions: list[dict],
    params: SimulationParams,
) -> dict | None:
    """인터랙티브 지정학 분석. 라운드 단위 실행 + DecisionPoint 일시정지."""
    # 1. 엔진 초기화 (기존 _step_geopolitics_analysis와 동일)
    engine = self._init_geopolitics_engine(actions)

    total_rounds = params.geopolitics_rounds
    mode = params.geopolitics_mode
    player_actor_id = params.geopolitics_player_actor_id
    threshold = params.geopolitics_pause_threshold

    all_round_results = []

    for round_num in range(1, total_rounds + 1):
        # 2. 라운드 1개 실행
        round_result = engine.run_single_round()
        all_round_results.append(round_result)

        # 3. DB에 이벤트 저장 (기존 로직)
        await self._save_geopolitics_events(scenario_id, result_id, round_result)

        # 4. 일시정지 판정
        if should_pause(round_result, mode, player_actor_id, threshold):
            # 5. 엔진 상태 스냅샷 저장
            snapshot_id = await self._save_geopolitics_snapshot(
                scenario_id, result_id, round_num, engine, mode, player_actor_id,
            )

            # 6. DecisionPoint 생성
            if mode == GeopoliticsMode.ACTOR_ROLE:
                trigger_event = self._find_trigger_event(round_result, player_actor_id)
                options = build_actor_response_options(engine, player_actor_id, trigger_event)
                dp_type = "geopolitics_actor_response"
                recommended = next((o["id"] for o in options if o["data"]["engine_recommended"]), options[0]["id"])
            else:
                options = build_direction_options(round_result)
                dp_type = "geopolitics_direction"
                recommended = "maintain"

            dp_id = await self._create_decision_point(
                scenario_id, dp_type, options, recommended,
            )

            # 7. 스냅샷에 decision_point_id 연결
            await self._link_snapshot_to_dp(snapshot_id, dp_id)

            # 8. 상태를 paused로 변경하고 리턴 (사용자 선택 대기)
            await self._update_status(scenario_id, result_id, "simulating:geopolitics_paused")
            return {"status": "paused", "round": round_num, "decision_point_id": dp_id}

    # 모든 라운드 완료 (일시정지 없이)
    return self._aggregate_geopolitics_results(all_round_results)
```

### 3.8 재개 로직

```python
# backend/app/routers/simulation.py — continue_pipeline() 확장

# status == "simulating:geopolitics_paused" 처리 추가

async def _continue_geopolitics(scenario_id: str, result_id: str):
    """지정학 일시정지에서 재개. DecisionPoint 선택을 반영하고 나머지 라운드 실행."""

    # 1. 스냅샷 복원
    snapshot = await _get_latest_geopolitics_snapshot(scenario_id, result_id)
    engine = DecisionEngine.from_state(json.loads(snapshot["engine_state"]))
    mode = GeopoliticsMode(snapshot["geopolitics_mode"])
    player_actor_id = snapshot.get("player_actor_id")

    # 2. DecisionPoint 해소 결과 가져오기
    dp = await _get_resolved_decision_point(snapshot["pending_decision_point_id"])

    # 3. 선택 반영
    if mode == GeopoliticsMode.ACTOR_ROLE:
        selected_action = dp.selected_option_id  # "diplomatic_statement" 등
        engine.override_next_action(player_actor_id, selected_action)

    elif mode == GeopoliticsMode.GAME_MASTER:
        selected = next(o for o in dp.options if o["id"] == dp.selected_option_id)
        deltas = selected["data"]["state_deltas"]
        applies_to = selected["data"]["applies_to"]
        engine.apply_direction_deltas(deltas, applies_to)

    # 4. 나머지 라운드 실행 (재귀적으로 _step_geopolitics_interactive 호출)
    remaining_rounds = params.geopolitics_rounds - snapshot["round_number"]
    # ... 나머지 라운드 실행, 다시 should_pause() 체크 ...
```

### 3.9 프론트엔드

```
# 수정 대상
frontend/src/components/simulation/DecisionPointView.tsx   # 2개 타입 추가 렌더링
frontend/src/components/simulation/SimulationPanel.tsx     # geopolitics_paused 상태 처리
frontend/src/components/simulation/PipelineProgress.tsx    # paused 상태 표시
frontend/src/types/simulation.ts                          # GeopoliticsMode 타입

# 신규
frontend/src/components/simulation/GeopoliticsDecisionView.tsx  # 지정학 선택 전용 UI
```

**GeopoliticsDecisionView 구성:**

| 영역 | Actor Role 모드 | Game Master 모드 |
|------|----------------|-----------------|
| 상단 | 트리거 이벤트 상세 (source→action→targets, magnitude) | 라운드 결과 요약 (전체 이벤트 목록, cascade 표시) |
| 중단 | 내 국가 상태 바 (threat, pressure, resource + 변화량) | 전체 긴장도 게이지 + actor별 상태 미니맵 |
| 하단 | 행동 선택 카드 7종 (엔진 추천 배지 + 예상 효과) | 방향 선택 카드 4종 (state delta 미리보기) |

---

## 4. 마일스톤

- [ ] **M1: DecisionEngine 라운드 분리** — `run_single_round()`, `override_next_action()`, `apply_direction_deltas()`, `serialize_state()`, `from_state()` 추가. 기존 `run_simulation()`은 내부적으로 `run_single_round()` 반복 호출로 리팩토링. auto 모드 동작 불변 검증.
  - 검증: 기존 auto 모드로 시뮬레이션 실행 → 결과 동일 (regression 없음)

- [ ] **M2: SimulationParams + DecisionPointType 확장** — `GeopoliticsMode` enum, `geopolitics_player_actor_id`, `geopolitics_rounds`, `geopolitics_pause_threshold` 추가. `GEOPOLITICS_ACTOR_RESPONSE`, `GEOPOLITICS_DIRECTION` 타입 추가. DB 스키마(`geopolitics_snapshots` 테이블) 생성.
  - 검증: 시나리오 생성 시 `geopolitics_mode: "actor_role"` 설정 가능. DB 테이블 존재.

- [ ] **M3: 일시정지 + 선택지 생성 + 재개** — `should_pause()`, `build_actor_response_options()`, `build_direction_options()` 구현. `_step_geopolitics_interactive()` orchestrator 통합. `continue_pipeline()`에서 `geopolitics_paused` 상태 처리. 스냅샷 저장/복원.
  - 검증: actor_role 모드로 시뮬레이션 → magnitude ≥ 0.5 이벤트에서 정지 → DecisionPoint 생성 확인 → resolve → 재개 → 다음 라운드 실행 확인

- [ ] **M4: GeopoliticsDecisionView 프론트엔드** — Actor Role UI (트리거 이벤트 + 내 국가 상태 + 행동 선택 7종). Game Master UI (라운드 요약 + 긴장도 게이지 + 방향 선택 4종). DecisionPointView.tsx에서 타입별 분기. PipelineProgress에 `geopolitics_paused` 상태 표시.
  - 검증: 두 모드 모두 UI에서 선택지 표시 → 선택 → 시뮬레이션 재개 확인

- [ ] **M5: 시뮬레이션 설정 UI** — 시나리오 생성/파라미터 설정에서 `geopolitics_mode` 선택 드롭다운. actor_role 선택 시 actor 목록 드롭다운 (시드 생성 후 에이전트 목록에서). 일시정지 임계치 슬라이더.
  - 검증: UI에서 모드 선택 → 시뮬레이션 시작 → 해당 모드로 지정학 분석 실행

---

## 5. 성공 기준

- auto 모드는 현재 동작과 100% 동일하다 (regression 없음)
- actor_role 모드에서 분석관이 특정 국가의 행동을 선택하면, 해당 선택이 다음 라운드에 반영된다
- game_master 모드에서 분석관이 시나리오 방향을 선택하면, 모든 관련 actor의 state가 조정된 후 다음 라운드가 진행된다
- 낮은 긴장도(magnitude < threshold) 라운드는 자동으로 진행되어 불필요한 클릭이 없다
- 일시정지 후 30분 초과 시 자동 재개된다
- 선택 결과가 이후 인과율 분석(CausalLogCollector)에 반영된다

---

## 6. 위험 및 완화

| 위험 | 완화 |
|------|------|
| 지정학 라운드가 3개뿐이라 선택 효과가 체감되지 않을 수 있음 | `geopolitics_rounds` 파라미터로 5~10까지 확장 가능하게 설계. 라운드 수가 늘면 선택의 누적 효과가 명확해짐 |
| actor_role에서 "어떤 국가를 선택해야 하나" 혼란 | 시드 생성 시 주요 행위자 목록을 보여주고, 가장 활발한 actor를 기본 추천 |
| 매 라운드 정지 시 피로감 | threshold 기본값을 0.5로 설정. 낮은 긴장도 라운드는 자동 진행. 사용자가 임계치 조정 가능 |
| 엔진 상태 직렬화 크기 | actor 10명 기준 JSON ~5KB. PostgreSQL TEXT 컬럼으로 충분 |
| 사용자 선택이 CausalLogCollector와 불일치 | 사용자 오버라이드 행동도 동일하게 geopolitics_events에 저장. CausalLogCollector는 DB 기준으로 수집하므로 자동 반영 |

---

## 진행 로그

| 날짜 | 상태 | 내용 |
|------|------|------|
| 2026-03-30 | Draft | V9 인터랙티브 지정학 듀얼 모드 PRD 초안 작성 |
