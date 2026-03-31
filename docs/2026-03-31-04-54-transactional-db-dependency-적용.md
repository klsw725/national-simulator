## 사용자 프롬프트

```
## TASK
Add a transactional database dependency `get_db_tx()` and apply it to endpoints that perform multiple writes across different tables.

## EXPECTED OUTCOME
- New `get_db_tx()` function in `database.py`
- Multi-write endpoints use `get_db_tx` instead of `get_db`
- Single-write and read-only endpoints stay on `get_db`
- Server starts successfully

## REQUIRED TOOLS
- Read, Edit, Bash

## MUST DO

### Step 1: Add `get_db_tx()` to `/home/swlee/osint-simulator/backend/app/database.py`

Add after the existing `get_db()` function:

```python
async def get_db_tx():
    """FastAPI dependency — yields a connection with an active transaction.
    
    Use for endpoints performing multiple writes across tables.
    All queries succeed together or roll back together.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            yield conn
```

### Step 2: Identify and update multi-write endpoints

Read each router file to find endpoints doing 2+ `conn.execute`/`conn.executemany` calls that write to different tables. Replace `conn: asyncpg.Connection = Depends(get_db)` with `conn: asyncpg.Connection = Depends(get_db_tx)`.

**`/home/swlee/osint-simulator/backend/app/routers/seed.py`**:
- `generate_seed` — INSERT seeds + INSERT scenario_observations + UPDATE scenarios → **USE get_db_tx**
- `generate_seed_options` — INSERT decision_points + UPDATE? → **Check and USE get_db_tx if multi-table**
- `recommend_params` — INSERT decision_points only → check if single table
- `get_seed` — read only → KEEP get_db

**`/home/swlee/osint-simulator/backend/app/routers/simulation_run.py`**:
- `start_simulation` — INSERT simulation_results + UPDATE scenarios (all 3 modes) → **USE get_db_tx**
- `continue_pipeline` — MANY writes across multiple tables → **USE get_db_tx**
- `get_checkpoint` — read only → KEEP get_db
- `retry_simulation` — read only (background task does writes) → KEEP get_db
- `get_simulation_status` — read only → KEEP get_db
- `get_simulation_results` — read only → KEEP get_db
- `get_geojson` — read + 1 UPDATE (cache) → KEEP get_db (single table)
- `get_report` — read only → KEEP get_db

**`/home/swlee/osint-simulator/backend/app/routers/decision_point.py`**:
- `create_decision_point` — INSERT + SELECT (same table) → KEEP get_db
- `resolve_decision_point` — UPDATE + SELECT (same table) → KEEP get_db

**`/home/swlee/osint-simulator/backend/app/routers/simulation_interactive.py`**:
- `pause_simulation` — UPDATE simulation_results + UPDATE scenarios → **USE get_db_tx**
- `resume_simulation` — UPDATE simulation_results + UPDATE scenarios → **USE get_db_tx**
- `inject_event` — INSERT injected_events only → KEEP get_db
- Others — read only or MiroFish proxies → KEEP get_db

**`/home/swlee/osint-simulator/backend/app/routers/scenario.py`**:
- Read the file to check. If any endpoint does multi-table writes → USE get_db_tx

### Step 3: Update imports
In each modified router file, add `get_db_tx` to the import from `app.database`:
```python
from app.database import get_db, get_db_tx
```

### Step 4: Verify
Run: `cd /home/swlee/osint-simulator/backend && uv run python -c "from app.main import app; print(f'OK: {len(app.routes)} routes')"`

## MUST NOT DO
- Do NOT change any SQL queries
- Do NOT change any business logic
- Do NOT add transactions to read-only endpoints
- Do NOT add transactions to single-table-write endpoints
- Do NOT modify the existing `get_db()` function
- Do NOT add error handling or retry logic around transactions — asyncpg handles rollback automatically on exception

## CONTEXT
- asyncpg's `conn.transaction()` context manager auto-commits on success, auto-rolls-back on exception
- The `_generate_decision_options` background task in simulation_run.py uses `get_pool()` directly — leave it alone
- The `continue_pipeline` endpoint is the most complex with many conditional writes — use get_db_tx for the whole endpoint
- AGENTS.md: "외과적 변경"
```

## 변경 요약

- `backend/app/database.py`
  - `get_db()` 아래에 `get_db_tx()` FastAPI 의존성을 추가함.
  - `pool.acquire()` + `conn.transaction()` 컨텍스트로 트랜잭션 범위를 구성함.

- `backend/app/routers/seed.py`
  - `from app.database import get_db, get_db_tx`로 import 확장.
  - `generate_seed`의 DB 의존성을 `Depends(get_db_tx)`로 변경.
  - `generate_seed_options`, `recommend_params`, `get_seed`는 기존 `get_db` 유지.

- `backend/app/routers/simulation_run.py`
  - `from app.database import get_db, get_db_tx, get_pool`로 import 확장.
  - `start_simulation` DB 의존성을 `Depends(get_db_tx)`로 변경.
  - `continue_pipeline` DB 의존성을 `Depends(get_db_tx)`로 변경.
  - 기타 read/single-write 엔드포인트는 `get_db` 유지.

- `backend/app/routers/simulation_interactive.py`
  - `from app.database import get_db, get_db_tx`로 import 확장.
  - `pause_simulation`, `resume_simulation` DB 의존성을 `Depends(get_db_tx)`로 변경.
  - `inject_event` 및 기타 엔드포인트는 `get_db` 유지.

- `backend/app/routers/scenario.py`
  - 멀티테이블 write 엔드포인트 없음 확인. 변경 없음.

## 검증

- 서버 import/route 초기화 확인:
  - `uv run python -c "from app.main import app; print(f'OK: {len(app.routes)} routes')"`
  - 결과: `OK: 102 routes`
