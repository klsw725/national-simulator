# Long-Idle Wargame Decision Flow Investigation

**Date:** 2026-04-01  
**Scope:** Backend TTL auto-complete, heartbeat loop, continue/resume paths, frontend state transitions  
**Focus:** Race conditions and duplicate decision handling when user leaves decision prompt unanswered for extended time

---

## Executive Summary

The wargame idle-timeout flow has **multiple race condition vectors** when a decision point remains unresolved for longer than `wargame_idle_ttl_minutes` (default 30 min):

1. **TTL Auto-Complete Race:** Backend auto-completes decision → emits `decision_auto_completed` SSE → calls `_continue_wargame()` (with `skip_cancel_heartbeat=True`)
2. **Concurrent User Decision:** User submits decision via `resolveWargameDecision()` → backend resolves DP → calls `resumeWargame()` → calls `_continue_wargame()` (with `skip_cancel_heartbeat=False`)
3. **Heartbeat Task Lifecycle:** Single `asyncio.Task` per `result_id` stored in `_wargame_heartbeat_tasks` dict; cancellation is **not atomic** with decision resolution
4. **Frontend SSE Reconnection:** Frontend may miss `decision_auto_completed` event if SSE drops; polling fallback has 5s interval but no deduplication

**Root Cause:** No mutual exclusion between TTL expiry and user decision submission. Both paths call `_continue_wargame()` independently, potentially executing the round loop twice in parallel.

---

## Architecture Overview

### Backend Flow: Pause → Heartbeat → TTL Expiry → Auto-Continue

```
_run_wargame_round_loop()
  ↓
  [Decision required, should_pause=true]
  ↓
  create_geopolitics_decision_point() → dp_id
  link_snapshot_to_dp(snapshot_id, dp_id)
  emit SSE: "decision_required"
  status = "wargame:paused:round_N"
  ↓
  _cancel_heartbeat_task(result_id)  [cancel any prior task]
  heartbeat_task = asyncio.create_task(_start_heartbeat_loop(...))
  _wargame_heartbeat_tasks[result_id] = heartbeat_task
  ↓
  return "paused", round_num
```

### Heartbeat Loop: 30-Second Intervals Until TTL Expires

**File:** `backend/app/services/simulation_orchestrator.py:808–924`

```python
async def _start_heartbeat_loop(
    scenario_id, result_id, mf_simulation_id, simulation_params, total_rounds, current_round
):
    ttl_minutes = simulation_params.wargame_idle_ttl_minutes  # default: 30
    deadline = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)
    
    while datetime.now(timezone.utc) < deadline:
        await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)  # 30 sec
        
        # Check if decision was resolved by user
        if await self._is_latest_decision_resolved(scenario_id, result_id):
            return  # Exit heartbeat loop, let user's continue path take over
        
        # Send heartbeat to MiroFish
        await self._send_control_signal(mf_simulation_id, {"type": "heartbeat", "timestamp": ts})
        
        # Emit SSE heartbeat event
        await self._emit_sse(scenario_id, "heartbeat", {...})
        
        # Update wargame_state with last_heartbeat timestamp
        await self._save_wargame_state(..., status="paused", last_heartbeat=ts)
    
    # TTL EXPIRED: deadline reached
    auto_outcome = await self._auto_complete_latest_decision(scenario_id, result_id)
    
    if not auto_outcome:
        # No pending decision to auto-complete
        await self._emit_sse(scenario_id, "phase_change", 
            {"phase": "briefing", "round": current_round, "status": "idle_timeout_no_pending_decision"})
        return
    
    # Auto-complete succeeded: emit SSE and continue
    await self._emit_sse(scenario_id, "decision_auto_completed", {...})
    await self._emit_sse(scenario_id, "phase_change", 
        {"phase": "simulation", "round": current_round + 1, "status": "idle_timeout_auto_continue"})
    
    try:
        await self._continue_wargame(
            scenario_id, result_id, simulation_params,
            previous_decision_outcome=auto_outcome,
            skip_cancel_heartbeat=True  # ← CRITICAL: Don't cancel self
        )
    except Exception:
        logger.exception("[%s] TTL auto-continue failed", scenario_id)
        await self._update_status(scenario_id, result_id, "failed")
```

### Auto-Complete Decision Logic

**File:** `backend/app/services/simulation_orchestrator.py:690–770`

```python
async def _auto_complete_latest_decision(scenario_id, result_id):
    snapshot = await get_latest_snapshot(scenario_id, result_id)
    if not snapshot:
        return None
    
    pending_dp_id = snapshot.get("pending_decision_point_id")
    if not pending_dp_id:
        return None
    
    pool = get_pool()
    async with pool.acquire() as conn:
        dp_row = await conn.fetchrow(
            "SELECT id, status, recommended, options, selected_option_id FROM decision_points WHERE id = $1",
            pending_dp_id
        )
        if not dp_row:
            return None
        
        # Determine selected option
        selected_option_id = dp_row["selected_option_id"] or dp_row["recommended"]
        if dp_row["status"] != "resolved":
            selected_option_id = dp_row["recommended"]
            if not selected_option_id:
                options = json.loads(dp_row["options"]) if dp_row["options"] else []
                if options:
                    selected_option_id = options[0].get("id")
            if not selected_option_id:
                return None
        
        # UPDATE decision_points SET status='resolved' WHERE id=$1 AND status='pending'
        # ← Uses WHERE status='pending' to prevent double-update
        now = datetime.now(timezone.utc).isoformat()
        auto_custom_data = json.dumps({
            "auto_completed": True,
            "reason": "idle_ttl_expired",
            "resolved_by": "system",
        })
        update_result = await conn.execute(
            """UPDATE decision_points
               SET status = 'resolved', selected_option_id = $1, custom_data = $2, resolved_at = $3
               WHERE id = $4 AND status = 'pending'""",
            selected_option_id, auto_custom_data, now, pending_dp_id
        )
        
        # Check if update succeeded (returns "UPDATE 1" if 1 row affected)
        if not str(update_result).endswith("1"):
            status = await conn.fetchval("SELECT status FROM decision_points WHERE id = $1", pending_dp_id)
            if status != "resolved":
                return None  # ← Decision was not resolved; abort auto-complete
    
    # Emit SSE events
    await self._emit_sse(scenario_id, "decision_auto_completed", {...})
    await ActionLogger.log("wargame.decision_auto_completed", scenario_id, {...})
    
    return outcome_message
```

**Key:** The `WHERE status = 'pending'` clause prevents double-update, but does NOT prevent two concurrent `_continue_wargame()` calls.

### User Decision Resolution Path

**File:** `backend/app/routers/decision_point.py` (inferred from usage)

```
POST /api/scenario/{scenario_id}/decision/{decision_point_id}/resolve
  ↓
  UPDATE decision_points SET status='resolved', selected_option_id=$1, resolved_at=$2 WHERE id=$3
  ↓
  emit SSE: "decision_resolved"
  ↓
  POST /api/scenario/{scenario_id}/continue
    ↓
    orchestrator.continue_wargame(scenario_id, result_id, simulation_params)
      ↓
      _continue_wargame(scenario_id, result_id, simulation_params, skip_cancel_heartbeat=False)
        ↓
        await self._cancel_heartbeat_task(result_id)  [Cancel heartbeat task]
        ↓
        [Resume round loop from snapshot round + 1]
```

### Continue Wargame: Resume from Snapshot

**File:** `backend/app/services/simulation_orchestrator.py:1209–1370`

```python
async def _continue_wargame(
    scenario_id, result_id, simulation_params,
    previous_decision_outcome=None,
    skip_cancel_heartbeat=False
):
    # 1. Fetch MiroFish simulation ID
    mf_simulation_id = await conn.fetchval("SELECT mirofish_simulation_id FROM simulation_results WHERE id = $1", result_id)
    
    # 2. Cancel heartbeat task (unless skip_cancel_heartbeat=True)
    if not skip_cancel_heartbeat:
        await self._cancel_heartbeat_task(result_id)
    
    # 3. Get MiroFish runner status
    run_status = await self.mf.get_run_status(mf_simulation_id)
    runner_status = str(run_status.get("runner_status", "")).lower()
    
    # 4. If runner not in {running, paused}, restart wargame process
    if runner_status not in {"running", "paused"}:
        ready_signal = await self._start_wargame_process(mf_simulation_id, total_rounds_for_restart, simulation_params)
        # ... validate ready_signal
    
    # 5. Fetch latest snapshot and decision point
    snapshot = await get_latest_snapshot(scenario_id, result_id)
    dp_row = await conn.fetchrow(
        "SELECT type, options, selected_option_id, custom_data FROM decision_points WHERE id = $1 AND status = 'resolved'",
        snapshot.get("pending_decision_point_id")
    )
    if not dp_row:
        raise RuntimeError("Decision point is not resolved")
    
    # 6. Reconstruct engine from snapshot
    engine_state = json.loads(snapshot["engine_state"])
    engine = DecisionEngine.from_state(engine_state)
    
    # 7. Apply user decision to engine
    selected_option = dp_row["selected_option_id"]
    if mode == GeopoliticsMode.ACTOR_ROLE:
        engine.override_next_action(actor_id, selected_option)
    elif mode == GeopoliticsMode.GAME_MASTER:
        engine.apply_direction_deltas(deltas, applies_to)
    
    # 8. Build inject_context with user decision
    inject_context = build_inject_context(engine, {...}, user_decision={...})
    
    # 9. Emit SSE: decision_resolved + phase_change
    await self._emit_sse(scenario_id, "decision_resolved", {...})
    await self._emit_sse(scenario_id, "phase_change", {"phase": "simulation", "round": snapshot["round_number"] + 1})
    
    # 10. Resume round loop from snapshot round + 1
    loop_status, _ = await self._run_wargame_round_loop(
        scenario_id, result_id, mf_simulation_id,
        start_round=int(snapshot["round_number"]) + 1,
        total_rounds=total_rounds,
        simulation_params=simulation_params,
        engine=engine,
        inject_context=inject_context,
        previous_decision_outcome=previous_decision_outcome
    )
    
    if loop_status == "paused":
        return  # Another decision point encountered
    
    # 11. Finalize wargame
    await self._finalize_wargame(scenario_id, result_id, mf_simulation_id, simulation_params, total_rounds)
```

---

## Race Condition Scenarios

### Scenario 1: TTL Expiry Wins (Heartbeat Completes First)

```
T0:  User leaves decision unanswered
T30: Heartbeat loop checks _is_latest_decision_resolved() → False
T60: Heartbeat loop checks _is_latest_decision_resolved() → False
...
T1800 (30 min): Deadline reached
     ↓
     _auto_complete_latest_decision() → UPDATE decision_points SET status='resolved' WHERE status='pending'
     ↓
     emit SSE: "decision_auto_completed"
     ↓
     _continue_wargame(..., skip_cancel_heartbeat=True)
       ↓
       [Does NOT cancel heartbeat task — task is already exiting]
       ↓
       _run_wargame_round_loop(start_round=N+1, ...)
       ↓
       [Resumes simulation]

T1801: User finally submits decision
     ↓
     POST /api/scenario/{id}/decision/{dp_id}/resolve
     ↓
     UPDATE decision_points SET status='resolved' WHERE id=$1
     ↓
     [Already resolved by TTL auto-complete; no-op]
     ↓
     POST /api/scenario/{id}/continue
     ↓
     orchestrator.continue_wargame()
     ↓
     _continue_wargame(..., skip_cancel_heartbeat=False)
       ↓
       _cancel_heartbeat_task(result_id)  [Task already done; no-op]
       ↓
       _run_wargame_round_loop(start_round=N+1, ...)
       ↓
       [DUPLICATE: Runs same round loop again!]
```

**Outcome:** Round N+1 executes twice, potentially with different decisions (auto-complete vs. user).

---

### Scenario 2: User Decision Wins (User Submits Before TTL)

```
T0:   User leaves decision unanswered
T30:  Heartbeat loop checks _is_latest_decision_resolved() → False
...
T900 (15 min): User submits decision
     ↓
     POST /api/scenario/{id}/decision/{dp_id}/resolve
     ↓
     UPDATE decision_points SET status='resolved', selected_option_id=$1 WHERE id=$1
     ↓
     emit SSE: "decision_resolved"
     ↓
     POST /api/scenario/{id}/continue
     ↓
     orchestrator.continue_wargame(..., skip_cancel_heartbeat=False)
       ↓
       _cancel_heartbeat_task(result_id)  [Cancels heartbeat task]
       ↓
       _run_wargame_round_loop(start_round=N+1, ...)
       ↓
       [Resumes simulation with user decision]

T930: Heartbeat loop wakes up, checks _is_latest_decision_resolved()
     ↓
     SELECT status FROM decision_points WHERE id = $1
     ↓
     status = 'resolved' (set by user)
     ↓
     return  [Exit heartbeat loop gracefully]
```

**Outcome:** Clean exit; no race condition.

---

### Scenario 3: Race Between TTL Auto-Complete and User Decision

```
T1799 (29:59): Heartbeat loop checks deadline
     ↓
     datetime.now() < deadline → True (1 second left)
     ↓
     await asyncio.sleep(30)  [Sleep for 30 seconds]

T1800 (30:00): Deadline reached
     ↓
     while loop condition: datetime.now() < deadline → False
     ↓
     Exit loop, proceed to auto-complete

T1800 (same moment): User submits decision
     ↓
     POST /api/scenario/{id}/decision/{dp_id}/resolve
     ↓
     UPDATE decision_points SET status='resolved' WHERE id=$1

T1800+ε: _auto_complete_latest_decision() executes
     ↓
     UPDATE decision_points SET status='resolved' WHERE id=$1 AND status='pending'
     ↓
     [WHERE status='pending' fails; decision already resolved by user]
     ↓
     Check: if not str(update_result).endswith("1"):
            status = await conn.fetchval("SELECT status FROM decision_points WHERE id = $1")
            if status != "resolved":
                return None  [Abort auto-complete]
     ↓
     [status = 'resolved'; continue auto-complete anyway]
     ↓
     emit SSE: "decision_auto_completed"
     ↓
     _continue_wargame(..., skip_cancel_heartbeat=True)

T1800+2ε: User's continue request arrives
     ↓
     POST /api/scenario/{id}/continue
     ↓
     orchestrator.continue_wargame(..., skip_cancel_heartbeat=False)
     ↓
     _cancel_heartbeat_task(result_id)  [Task already exiting; no-op]
     ↓
     _run_wargame_round_loop(start_round=N+1, ...)
     ↓
     [DUPLICATE: Runs same round loop again!]
```

**Outcome:** Both auto-complete and user decision paths execute `_continue_wargame()` concurrently, causing duplicate round execution.

---

## Frontend State Transitions

**File:** `frontend/src/hooks/useWargame.ts`

### SSE Event Handlers

```typescript
const handleSSEEvent = useCallback((event: MessageEvent) => {
  const data = JSON.parse(event.data);
  const eventType = event.type || data.type;
  
  switch (eventType) {
    case "phase_change":
      setState((prev) => ({
        ...prev,
        phase: data.phase,
        round: data.round ?? prev.round,
        // FIX: Clear stale briefing/decision when phase changes
        ...(data.phase === "briefing" || data.phase === "simulation"
          ? { briefing: null, decisionPoint: null }
          : {}),
      }));
      break;
    
    case "decision_auto_completed":
      // Record auto-completed decision in history
      setDecisionHistory((prev) => {
        const effectiveRound = data.round || prev.length + 1;
        if (prev.some((d) => d.round === effectiveRound)) return prev;
        return [
          ...prev,
          {
            round: effectiveRound,
            label: data.selected ?? "자동 결정",
            outcome: data.outcome ?? "TTL 만료로 자동 결정되었습니다.",
          },
        ];
      });
      break;
    
    case "decision_resolved":
      // Record user decision in history
      setDecisionHistory((prev) => {
        const effectiveRound = data.round ?? 0;
        if (prev.some((d) => d.round === effectiveRound)) return prev;
        return [
          ...prev,
          { round: effectiveRound, label: data.label ?? "결정", outcome: data.outcome ?? "결정 반영됨" },
        ];
      });
      setState((prev) => ({
        ...prev,
        phase: "confirmation",
        decisionPoint: null,
      }));
      break;
  }
}, [hydrateFromBackend]);
```

### Heartbeat Timeout & Reconnection

```typescript
const resetHeartbeatTimer = useCallback(() => {
  if (heartbeatRef.current) clearTimeout(heartbeatRef.current);
  heartbeatRef.current = setTimeout(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setIsConnected(false);
    reconnectAttemptsRef.current += 1;
    if (reconnectAttemptsRef.current <= SSE_MAX_RECONNECT_ATTEMPTS) {
      const delay = SSE_RECONNECT_DELAY * reconnectAttemptsRef.current;
      reconnectRef.current = setTimeout(() => connectSSE(), delay);
    } else {
      setIsMockMode(true);
      startPollingFallback();  // Fall back to 5-second polling
    }
  }, SSE_HEARTBEAT_TIMEOUT);  // 300 seconds (5 minutes)
}, [startPollingFallback]);
```

**Issue:** If SSE drops during TTL auto-complete, frontend may miss `decision_auto_completed` event and fall back to polling. Polling interval is 5 seconds; if auto-complete happens between polls, frontend may not see it until next poll.

### WarRoom Decision Confirmation

**File:** `frontend/src/components/wargame/WarRoom.tsx:96–134`

```typescript
const handleDecisionConfirm = async (selectedOptionId: string) => {
  const dp = wargame.state.decisionPoint;
  if (!dp) return;
  
  const selectedOption = dp.options.find((o) => o.id === selectedOptionId);
  wargame.recordDecision({
    round: wargame.state.round,
    label: selectedOption?.label ?? selectedOptionId,
    outcome: selectedOption?.reasoning ?? "결정 반영됨",
  });
  
  wargame.setPhase("confirmation");
  
  if (resumePollRef.current) {
    clearInterval(resumePollRef.current);
    resumePollRef.current = null;
  }
  
  try {
    await resolveWargameDecision(scenarioId, dp.id, selectedOptionId);
    await resumeWargame(scenarioId);
  } catch (err) {
    if (process.env.NODE_ENV === "development") {
      console.error("Failed to resolve/resume wargame:", err);
    }
  }
  
  // If SSE disconnected, poll for state updates
  if (!wargame.isConnected) {
    resumePollRef.current = setInterval(() => {
      wargame.refreshState().catch(() => {});
    }, 3000);
    setTimeout(() => {
      if (resumePollRef.current) {
        clearInterval(resumePollRef.current);
        resumePollRef.current = null;
      }
    }, 120_000);  // Stop polling after 2 minutes
  }
};
```

**Issue:** Frontend calls `resolveWargameDecision()` + `resumeWargame()` sequentially. If TTL auto-complete happens between these calls, both paths execute independently.

---

## Key Files & Functions

| File | Function | Purpose |
|------|----------|---------|
| `backend/app/services/simulation_orchestrator.py:808–924` | `_start_heartbeat_loop()` | Heartbeat loop; TTL expiry trigger |
| `backend/app/services/simulation_orchestrator.py:690–770` | `_auto_complete_latest_decision()` | Auto-complete decision on TTL expiry |
| `backend/app/services/simulation_orchestrator.py:1209–1370` | `_continue_wargame()` | Resume round loop from snapshot |
| `backend/app/services/simulation_orchestrator.py:1088–1099` | Heartbeat task creation | Store task in `_wargame_heartbeat_tasks[result_id]` |
| `backend/app/services/simulation_orchestrator.py:669–676` | `_cancel_heartbeat_task()` | Cancel heartbeat task |
| `backend/app/routers/simulation_run.py:294–460` | `continue_pipeline()` | User decision → continue endpoint |
| `backend/app/database.py` | `wargame_state` table | Stores `status`, `last_heartbeat`, `current_round` |
| `backend/app/database.py` | `decision_points` table | Stores `status`, `selected_option_id`, `resolved_at` |
| `frontend/src/hooks/useWargame.ts:257–382` | `handleSSEEvent()` | SSE event handler; decision history recording |
| `frontend/src/hooks/useWargame.ts:411–428` | `resetHeartbeatTimer()` | SSE heartbeat timeout & reconnection |
| `frontend/src/components/wargame/WarRoom.tsx:96–134` | `handleDecisionConfirm()` | User decision submission |

---

## Bug Hypotheses

### Hypothesis 1: Duplicate Round Execution (HIGH CONFIDENCE)

**Symptom:** Round N+1 executes twice with different decisions (auto-complete vs. user).

**Root Cause:** No mutual exclusion between TTL auto-complete and user decision paths. Both call `_continue_wargame()` independently.

**Evidence:**
- `_auto_complete_latest_decision()` updates decision_points and calls `_continue_wargame(..., skip_cancel_heartbeat=True)` (line 914)
- User decision path calls `_continue_wargame(..., skip_cancel_heartbeat=False)` (line 329 in simulation_run.py)
- No lock or atomic check prevents both from executing concurrently
- `_cancel_heartbeat_task()` is not atomic; task may already be exiting

**Fix:** Add a lock or atomic flag to prevent concurrent `_continue_wargame()` calls for the same `result_id`.

---

### Hypothesis 2: Heartbeat Task Lifecycle Confusion (MEDIUM CONFIDENCE)

**Symptom:** Heartbeat task not properly cancelled; stale task references remain in `_wargame_heartbeat_tasks` dict.

**Root Cause:** 
- `_cancel_heartbeat_task()` pops task from dict and cancels it, but doesn't wait for cancellation to complete
- If `_continue_wargame()` is called with `skip_cancel_heartbeat=True`, task is not cancelled
- Task may still be running when user decision arrives

**Evidence:**
- Line 670: `task = self._wargame_heartbeat_tasks.pop(result_id, None)` — removes from dict
- Line 671–676: Cancels task, but doesn't guarantee completion
- Line 919: `skip_cancel_heartbeat=True` in TTL auto-continue path

**Fix:** Ensure heartbeat task is fully cancelled before resuming round loop. Use `await task` after cancellation.

---

### Hypothesis 3: Frontend SSE Reconnection Race (MEDIUM CONFIDENCE)

**Symptom:** Frontend misses `decision_auto_completed` event; shows stale decision point UI.

**Root Cause:**
- SSE heartbeat timeout is 300 seconds (5 minutes)
- If SSE drops during TTL auto-complete (at 30 minutes), frontend doesn't reconnect immediately
- Polling fallback has 5-second interval; may miss auto-complete event

**Evidence:**
- Line 17: `SSE_HEARTBEAT_TIMEOUT = 300_000` (5 minutes)
- Line 384–409: `startPollingFallback()` uses 5-second interval
- Line 411–428: `resetHeartbeatTimer()` only resets on SSE events; doesn't reset on polling

**Fix:** Reduce SSE heartbeat timeout or ensure polling continues during idle periods.

---

### Hypothesis 4: Decision Point Status Check Race (LOW CONFIDENCE)

**Symptom:** `_is_latest_decision_resolved()` returns False even though decision was just resolved.

**Root Cause:**
- Heartbeat loop checks `_is_latest_decision_resolved()` every 30 seconds
- If user decision arrives between checks, heartbeat loop may not see it until next check
- Meanwhile, TTL deadline may be reached

**Evidence:**
- Line 821: `if await self._is_latest_decision_resolved(scenario_id, result_id): return`
- Line 820: `await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)` — 30-second interval
- No event-driven notification; only polling

**Fix:** Use database triggers or event bus to notify heartbeat loop of decision resolution.

---

## Event Sequence Diagrams

### Sequence 1: TTL Auto-Complete (Happy Path)

```
User                Backend                    MiroFish
  |                   |                           |
  |-- (idle 30 min)---|                           |
  |                   |                           |
  |                   |-- heartbeat loop -------->|
  |                   |<-- heartbeat_ack --------|
  |                   |                           |
  |                   |-- (repeat every 30s) --->|
  |                   |                           |
  |                   |-- TTL deadline reached   |
  |                   |                           |
  |                   |-- auto_complete_decision |
  |                   |   (UPDATE DP status)     |
  |                   |                           |
  |                   |-- emit SSE: decision_auto_completed
  |<-- SSE event -----|                           |
  |                   |                           |
  |                   |-- _continue_wargame() -->|
  |                   |   (skip_cancel_heartbeat=True)
  |                   |                           |
  |                   |-- proceed_round(N+1) --->|
  |                   |<-- round_complete -------|
  |                   |                           |
  |-- (late submit)---|                           |
  |-- POST /continue -|                           |
  |                   |-- _continue_wargame() -->|
  |                   |   (skip_cancel_heartbeat=False)
  |                   |                           |
  |                   |-- proceed_round(N+1) --->|  ← DUPLICATE!
  |                   |<-- round_complete -------|
  |                   |                           |
```

### Sequence 2: User Decision (Happy Path)

```
User                Backend                    MiroFish
  |                   |                           |
  |-- (idle 15 min)---|                           |
  |                   |                           |
  |-- POST /resolve --|                           |
  |                   |-- UPDATE DP status       |
  |                   |   (status='resolved')    |
  |                   |                           |
  |                   |-- emit SSE: decision_resolved
  |<-- SSE event -----|                           |
  |                   |                           |
  |-- POST /continue -|                           |
  |                   |-- _cancel_heartbeat_task |
  |                   |   (cancel task)          |
  |                   |                           |
  |                   |-- _continue_wargame() -->|
  |                   |   (skip_cancel_heartbeat=False)
  |                   |                           |
  |                   |-- proceed_round(N+1) --->|
  |                   |<-- round_complete -------|
  |                   |                           |
  |                   |-- (heartbeat loop exits) |
  |                   |   (checks _is_latest_decision_resolved)
  |                   |                           |
```

---

## Database Schema (Relevant Columns)

### `decision_points` Table

```sql
CREATE TABLE decision_points (
    id TEXT PRIMARY KEY,
    scenario_id TEXT NOT NULL,
    type TEXT NOT NULL,  -- 'geopolitics_actor_response', 'geopolitics_direction', etc.
    status TEXT NOT NULL,  -- 'pending', 'resolved'
    options JSONB,
    selected_option_id TEXT,
    custom_data JSONB,
    recommended TEXT,
    created_at TEXT,
    resolved_at TEXT,
    ...
);

CREATE INDEX idx_decision_points_status ON decision_points(status);
CREATE INDEX idx_decision_points_scenario_status ON decision_points(scenario_id, status);
CREATE INDEX idx_decision_points_scenario_type_status ON decision_points(scenario_id, type, status);
```

### `wargame_state` Table

```sql
CREATE TABLE wargame_state (
    id TEXT PRIMARY KEY,
    scenario_id TEXT NOT NULL,
    result_id TEXT NOT NULL,
    current_round INT,
    total_rounds INT,
    engine_state JSONB,
    process_pid INT,
    status TEXT,  -- 'running', 'paused', 'completed', 'crashed'
    last_heartbeat TEXT,
    created_at TEXT,
    updated_at TEXT,
    ...
);
```

### `geopolitics_snapshots` Table

```sql
CREATE TABLE geopolitics_snapshots (
    id TEXT PRIMARY KEY,
    scenario_id TEXT NOT NULL,
    result_id TEXT NOT NULL,
    round_number INT,
    engine_state JSONB,
    pending_decision_point_id TEXT,  -- FK to decision_points
    geopolitics_mode TEXT,
    player_actor_id TEXT,
    created_at TEXT,
    ...
);
```

---

## Configuration

**File:** `backend/app/models/scenario.py:28`

```python
wargame_idle_ttl_minutes: int = Field(
    default=30,
    ge=1,
    le=120,
    description="Max pause duration in minutes"
)
```

**File:** `backend/app/services/simulation_orchestrator.py:87`

```python
HEARTBEAT_INTERVAL_SECONDS = 30
```

---

## Recommendations

### Immediate Fixes (P0)

1. **Add Mutual Exclusion Lock**
   - Use `asyncio.Lock` per `result_id` to prevent concurrent `_continue_wargame()` calls
   - Acquire lock before checking decision status; release after round loop completes
   - Location: `backend/app/services/simulation_orchestrator.py`

2. **Atomic Decision Resolution Check**
   - Combine decision status check + heartbeat task cancellation into single atomic operation
   - Use database transaction to ensure heartbeat task is cancelled before decision is marked resolved
   - Location: `backend/app/services/simulation_orchestrator.py:_cancel_heartbeat_task()`

3. **Ensure Heartbeat Task Completion**
   - After cancelling heartbeat task, `await task` to ensure cancellation is complete
   - Handle `asyncio.CancelledError` gracefully
   - Location: `backend/app/services/simulation_orchestrator.py:669–676`

### Medium-Term Fixes (P1)

4. **Event-Driven Heartbeat Notification**
   - Use event bus or database trigger to notify heartbeat loop of decision resolution
   - Replace polling-based `_is_latest_decision_resolved()` with event-driven approach
   - Location: `backend/app/services/simulation_orchestrator.py:821`

5. **Frontend SSE Reconnection Improvement**
   - Reduce SSE heartbeat timeout from 5 minutes to 1 minute
   - Ensure polling continues during idle periods
   - Add deduplication logic for decision events
   - Location: `frontend/src/hooks/useWargame.ts:17, 384–409`

6. **Idempotent Continue Endpoint**
   - Add idempotency key to `POST /continue` endpoint
   - Prevent duplicate round execution if same request is retried
   - Location: `backend/app/routers/simulation_run.py:294–460`

### Long-Term Fixes (P2)

7. **Structured Concurrency**
   - Refactor wargame pipeline to use structured concurrency (e.g., `asyncio.TaskGroup`)
   - Ensure all background tasks are properly scoped and cancelled
   - Location: `backend/app/services/simulation_orchestrator.py`

8. **Comprehensive Logging**
   - Add detailed logging for decision resolution, heartbeat loop, and continue paths
   - Log all state transitions and race condition detection
   - Location: All affected functions

---

## Testing Strategy

### Unit Tests

1. **Test TTL Auto-Complete**
   - Mock time; advance clock to TTL deadline
   - Verify `_auto_complete_latest_decision()` is called
   - Verify decision_points table is updated
   - Verify SSE events are emitted

2. **Test User Decision During Heartbeat**
   - Start heartbeat loop
   - Submit user decision while loop is running
   - Verify heartbeat loop exits gracefully
   - Verify no duplicate round execution

3. **Test Concurrent TTL + User Decision**
   - Simulate TTL expiry and user decision arriving simultaneously
   - Verify only one `_continue_wargame()` call executes
   - Verify decision_points table is updated exactly once

### Integration Tests

4. **Test Full Idle Timeout Flow**
   - Start wargame; pause at decision point
   - Wait for TTL to expire
   - Verify auto-complete happens
   - Verify round loop resumes
   - Verify simulation completes

5. **Test User Decision Before TTL**
   - Start wargame; pause at decision point
   - Submit decision before TTL expires
   - Verify heartbeat loop exits
   - Verify round loop resumes with user decision
   - Verify simulation completes

6. **Test SSE Reconnection During TTL**
   - Start wargame; pause at decision point
   - Disconnect SSE
   - Wait for TTL to expire
   - Verify auto-complete happens
   - Verify polling detects auto-complete
   - Verify frontend state is updated

---

## Conclusion

The long-idle wargame decision flow has **critical race conditions** between TTL auto-complete and user decision submission. The root cause is the lack of mutual exclusion between two independent paths that both call `_continue_wargame()`. This can lead to:

1. **Duplicate round execution** with conflicting decisions
2. **Stale heartbeat task references** in memory
3. **Frontend state inconsistency** due to SSE reconnection delays

**Immediate action required:** Implement mutual exclusion lock to prevent concurrent `_continue_wargame()` calls for the same `result_id`.
