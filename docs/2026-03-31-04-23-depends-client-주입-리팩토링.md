# 작업 기록: Depends 기반 클라이언트 주입 리팩토링

## 사용자 프롬프트
```
## TASK
Replace direct `request.app.state.sb_client` / `request.app.state.mf_client` access with FastAPI `Depends()` injection across 6 router files.

## EXPECTED OUTCOME
- New dependency functions in `_helpers.py`
- All 28 instances of `request.app.state.*_client` replaced with `Depends()` parameters
- `request: Request` removed from endpoint signatures where it's no longer needed
- Server starts successfully

## REQUIRED TOOLS
- Read, Edit, Bash

## MUST DO

### Step 1: Add dependency functions to `/home/swlee/osint-simulator/backend/app/routers/_helpers.py`
Add these functions at the bottom of the existing file:

```python
from fastapi import Request
from app.clients.mirofish import MiroFishClient
from app.clients.shadowbroker import ShadowBrokerClient

def get_mf_client(request: Request) -> MiroFishClient:
    return request.app.state.mf_client

def get_sb_client(request: Request) -> ShadowBrokerClient:
    return request.app.state.sb_client
```

Note: NOT async — they just return the existing client instance.

### Step 2: Update each router file

For each file, the pattern is:

**Before:**
```python
async def some_endpoint(scenario_id: str, request: Request, conn = Depends(get_db)):
    sb_client = request.app.state.sb_client
    # use sb_client...
```

**After:**
```python
async def some_endpoint(scenario_id: str, sb_client: ShadowBrokerClient = Depends(get_sb_client), conn = Depends(get_db)):
    # use sb_client directly...
```

**Rules:**
1. Add `sb_client: ShadowBrokerClient = Depends(get_sb_client)` as a function parameter
2. Add `mf_client: MiroFishClient = Depends(get_mf_client)` as a function parameter
3. Remove the `sb_client = request.app.state.sb_client` line inside the function body
4. Remove `request: Request` from the function signature ONLY IF `request` is not used elsewhere in the function (check for `request.json()`, `request.body()`, etc.)
5. If the endpoint uses both clients, add both as Depends params
6. Add import for `get_mf_client`/`get_sb_client` from `app.routers._helpers` and for `MiroFishClient`/`ShadowBrokerClient` from their respective modules
7. Keep `Depends` import from fastapi

### Files to update:

**`seed.py`** (3 instances — all sb_client)
- Lines ~47, ~140, ~209: `sb_client = request.app.state.sb_client`
- All 3 endpoints can drop `request: Request` since they don't use it elsewhere

**`briefing.py`** (1 instance — sb_client)
- Line ~34: `sb_client = request.app.state.sb_client`
- Check if `request` is used elsewhere in that endpoint

**`simulation_run.py`** (7 instances — mix of both)
- Lines ~211, ~239, ~258, ~361, ~382, ~599, ~608
- Some endpoints use BOTH sb_client and mf_client
- The `_generate_decision_options` background task gets `sb_client` passed as argument — this must still work (the function parameter just sources from Depends now)
- IMPORTANT: `start_simulation` uses `request.app.state.sb_client` inline at line ~258 and ~211. Replace both.

**`simulation_live.py`** (6 instances — all mf_client)
- Lines ~29, ~52, ~77, ~97, ~118, ~138
- These endpoints also have `request: Request` — check if they use it for anything else

**`simulation_interactive.py`** (10 instances — mostly mf_client, some sb_client)
- Lines ~161-162, ~243, ~352, ~375, ~395, ~423, ~450, ~478, ~498
- Line 162: `sb_client=request.app.state.sb_client` in SimulationOrchestrator constructor
- Some endpoints use `request.json()` — KEEP `request: Request` for those
- `pause_simulation` (~line 80-ish in original) creates a new MiroFishClient inline — leave that as-is

**`osint.py`** (1 instance — sb_client)
- Line ~18: has its own inline dependency. Replace with shared `get_sb_client`

### Step 3: Verify
Run: `cd /home/swlee/osint-simulator/backend && uv run python -c "from app.main import app; print(f'OK: {len(app.routes)} routes')"`

## MUST NOT DO
- Do NOT change business logic
- Do NOT remove `request: Request` if the function still uses `request` for `request.json()`, `request.body()`, or other purposes
- Do NOT change the `_generate_decision_options` function signature — it receives clients as regular arguments
- Do NOT modify `main.py`
- Do NOT touch `simulation_interactive.py`'s `pause_simulation` which creates its own MiroFishClient inline

## CONTEXT
- Existing `_helpers.py` has: `get_sim_row`, `row_to_seed_response`, `row_to_decision_point`
- FastAPI `Depends()` automatically calls the function with the `Request` — we just declare the parameter
- Type annotations on Depends params are important for documentation/IDE support
```

## 변경 요약
- `backend/app/routers/_helpers.py`
  - `get_mf_client`, `get_sb_client` 의존성 함수 추가
  - `Request`, `MiroFishClient`, `ShadowBrokerClient` import 추가

- `backend/app/routers/seed.py`
  - 3개 엔드포인트에서 `request.app.state.sb_client` 제거
  - `sb_client: ShadowBrokerClient = Depends(get_sb_client)` 주입으로 변경
  - 불필요해진 `request: Request` 시그니처 제거

- `backend/app/routers/briefing.py`
  - `generate_briefing`에서 `sb_client` Depends 주입으로 변경
  - `update_briefing`는 `request.json()` 사용하므로 `request` 유지

- `backend/app/routers/simulation_run.py`
  - `start_simulation`, `retry_simulation`, `continue_pipeline`에서 `mf_client/sb_client` Depends 주입 추가
  - 함수 본문의 `request.app.state.*_client` 접근 제거
  - `_generate_decision_options` 시그니처는 변경하지 않고 호출부에서 주입받은 `sb_client` 전달 유지

- `backend/app/routers/simulation_live.py`
  - 6개 엔드포인트 모두 `mf_client` Depends 주입으로 변경
  - 사용되지 않는 `request: Request` 제거

- `backend/app/routers/simulation_interactive.py`
  - `resume_simulation`, `create_whatif_branch`, `compare_whatif_branch`, `get_env_status`, `interview_*`, `get_interview_history`, `close_simulation_env`에 Depends 주입 적용
  - `request.json()` 필요한 엔드포인트의 `request`는 유지
  - `pause_simulation`의 inline `MiroFishClient` 생성 로직은 그대로 유지

- `backend/app/routers/osint.py`
  - 로컬 `_get_sb` 제거, 공용 `get_sb_client`로 통일
  - 각 라우트에서 `ShadowBrokerClient = Depends(get_sb_client)` 주입 사용
  - `_proxy`가 `Request` 대신 주입된 `sb`를 직접 받도록 조정

## 검증
- 실행: `uv sync` (backend)
- 실행: `uv run python -c "from app.main import app; print(f'OK: {len(app.routes)} routes')"`
- 결과: `OK: 102 routes`

## 참고
- LSP diagnostics는 환경의 Pyright import 해석 문제(`reportMissingImports`)로 외부 패키지(`fastapi`, `asyncpg`, `httpx`) 미해결 경고가 지속됨.
- 런타임 import 검증(`uv run ... from app.main import app`)은 성공.
