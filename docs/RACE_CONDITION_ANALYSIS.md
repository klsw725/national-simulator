# Frontend Race Condition Analysis: Long-Idle Wargame Decisions

**Date:** 2026-04-01  
**Focus:** SSE/polling interaction during backend TTL auto-complete  
**Severity:** HIGH - UI state corruption, decision history loss, phase desync

---

## Executive Summary

When a user leaves a wargame decision unanswered for longer than the backend TTL (default: `wargame_idle_ttl_minutes`), the backend auto-completes the decision and emits a `decision_auto_completed` SSE event. However, **multiple race conditions exist** between:

1. **SSE event delivery** vs. **polling fallback** (when SSE disconnects)
2. **Phase state** vs. **decision history** (stale decision point in UI)
3. **Confirmation phase** vs. **auto-complete event** (double-resolution)
4. **Heartbeat timeout** vs. **manual user decision** (conflicting state updates)

This document maps exact code paths and failure modes.

---

## Architecture Overview

### Frontend State Machine (useWargame.ts)

```
useWargame Hook
├── state: WargameState (phase, round, decisionPoint, briefing)
├── decisionHistory: DecisionRecord[] (immutable append-only)
├── isConnected: boolean (SSE status)
├── isMockMode: boolean (fallback to polling)
└── Timers:
    ├── eventSourceRef (SSE connection)
    ├── pollRef (5s polling fallback)
    ├── heartbeatRef (300s SSE heartbeat timeout)
    └── reconnectRef (exponential backoff)
```

### Backend Wargame Loop (simulation_orchestrator.py)

```
run_wargame_pipeline()
├── _run_wargame_round_loop()
│   └── [Pause at decision point]
│       └── _start_heartbeat_loop() ← TTL TIMER STARTS HERE
│           ├── Emit "decision_required" SSE
│           ├── Wait for user decision (5s polling in frontend)
│           └── [TTL expires after wargame_idle_ttl_minutes]
│               └── _auto_complete_latest_decision()
│                   ├── Update DB: decision_points.status = 'resolved'
│                   ├── Emit "decision_auto_completed" SSE
│                   └── _continue_wargame()
└── _finalize_wargame()
    └── Emit "simulation_complete" SSE
```

---

## Race Condition #1: SSE Disconnect → Polling Fallback Desync

### Scenario
User leaves decision unanswered. SSE connection drops (network, timeout, etc.) **before** TTL expires.

### Code Path

**Frontend (useWargame.ts:430-490)**
```typescript
const connectSSE = useCallback(() => {
  // ... setup EventSource
  es.onerror = () => {
    setIsConnected(false);
    reconnectAttemptsRef.current += 1;
    if (reconnectAttemptsRef.current <= SSE_MAX_RECONNECT_ATTEMPTS) {  // 4 attempts
      const delay = SSE_RECONNECT_DELAY * reconnectAttemptsRef.current;  // 3s * attempt
      reconnectRef.current = setTimeout(() => connectSSE(), delay);
    } else {
      setIsMockMode(true);  // ← FALLBACK TO POLLING
      startPollingFallback();
    }
  };
}, [...]);
```

**Frontend (useWargame.ts:384-409)**
```typescript
const startPollingFallback = useCallback(() => {
  if (pollRef.current || !scenarioId) return;
  
  pollRef.current = setInterval(() => {
    getWargameStatus(scenarioId)
      .then((data) => {
        setState((prev) => ({ ...prev, ...data }));  // ← SHALLOW MERGE
        // ... tension history update
        if (data.phase === "confirmation" && !data.decisionPoint && data.round >= data.totalRounds) {
          setIsComplete(true);
        }
      })
      .catch(() => {});
  }, POLL_INTERVAL);  // 5000ms
}, [scenarioId]);
```

**Backend (simulation_orchestrator.py:817-823)**
```python
async def _start_heartbeat_loop(self, ...):
    ttl_minutes = simulation_params.wargame_idle_ttl_minutes
    deadline = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)
    while datetime.now(timezone.utc) < deadline:
        await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)  # 30s
        if await self._is_latest_decision_resolved(scenario_id, result_id):
            return  # ← User resolved manually
        # ... emit heartbeat SSE
```

### Failure Mode: **Stale Decision Point**

1. **T=0s:** SSE connected, user sees decision card
2. **T=30s:** SSE drops (network error)
3. **T=33s:** Frontend reconnect attempt #1 fails
4. **T=36s:** Frontend reconnect attempt #2 fails
5. **T=39s:** Frontend reconnect attempt #3 fails
6. **T=42s:** Frontend reconnect attempt #4 fails
7. **T=45s:** Frontend switches to polling (`isMockMode=true`)
8. **T=45-300s:** Polling fetches `wargame_status` every 5s
   - **Problem:** `getWargameStatus()` returns **latest** decision point from DB
   - If decision is still `pending`, polling keeps returning the **same stale decision point**
9. **T=300s:** Backend TTL expires
   - Backend auto-completes decision
   - Emits `decision_auto_completed` SSE (but SSE is dead)
   - Continues wargame
10. **T=305s:** Polling fetches status again
    - **Expected:** `phase="simulation"`, `decisionPoint=null`
    - **Actual:** Depends on race between:
      - Backend updating `wargame_state` table
      - Frontend polling reading stale cache

### Code Reference

**Frontend (useWargame.ts:384-409)** - Polling doesn't clear stale decision point
```typescript
// ❌ PROBLEM: If backend hasn't updated wargame_state yet,
// polling will return the OLD decision point again
setState((prev) => ({ ...prev, ...data }));
```

**Backend (simulation_orchestrator.py:759-770)** - SSE event lost if disconnected
```python
await self._emit_sse(
    scenario_id,
    "decision_auto_completed",  # ← Never reaches frontend if SSE is dead
    {
        "decision_point_id": pending_dp_id,
        "selected": selected_option_id,
        "outcome": outcome,
        "reason": "idle_ttl_expired",
        "round": int(snapshot.get("round_number") or 0),
    },
)
```

---

## Race Condition #2: Confirmation Phase Entered Before Auto-Complete Event

### Scenario
User manually resolves decision **just as** TTL expires.

### Code Path

**Frontend (WarRoom.tsx:96-134)**
```typescript
const handleDecisionConfirm = async (selectedOptionId: string) => {
  const dp = wargame.state.decisionPoint;
  if (!dp) return;
  
  wargame.recordDecision({...});
  wargame.setPhase("confirmation");  // ← IMMEDIATE UI UPDATE
  
  if (resumePollRef.current) {
    clearInterval(resumePollRef.current);
    resumePollRef.current = null;
  }
  
  try {
    await resolveWargameDecision(scenarioId, dp.id, selectedOptionId);  // ← API CALL
    await resumeWargame(scenarioId);
  } catch (err) {
    // ... error handling
  }
  
  if (!wargame.isConnected) {
    resumePollRef.current = setInterval(() => {
      wargame.refreshState().catch(() => {});
    }, 3000);
    setTimeout(() => {
      if (resumePollRef.current) {
        clearInterval(resumePollRef.current);
        resumePollRef.current = null;
      }
    }, 120_000);  // ← STOP POLLING AFTER 2 MINUTES
  }
};
```

**Backend (simulation_orchestrator.py:690-770)**
```python
async def _auto_complete_latest_decision(self, scenario_id, result_id):
    # ... fetch pending decision
    if dp_row["status"] != "resolved":
        selected_option_id = dp_row["recommended"]
        # ... auto-select
        update_result = await conn.execute(
            """UPDATE decision_points
               SET status = 'resolved', selected_option_id = $1, ...
               WHERE id = $4 AND status = 'pending'""",  # ← ONLY IF STILL PENDING
            ...
        )
        if not str(update_result).endswith("1"):  # ← UPDATE FAILED (already resolved)
            status = await conn.fetchval(
                "SELECT status FROM decision_points WHERE id = $1",
                pending_dp_id,
            )
            if status != "resolved":
                return None  # ← EARLY EXIT, NO SSE EVENT
```

### Failure Mode: **Missing Auto-Complete Event**

1. **T=0s:** Decision point created, TTL timer starts
2. **T=299s:** User clicks "결정 확정" button
3. **T=299.1s:** Frontend calls `resolveWargameDecision()` (POST)
4. **T=299.2s:** Backend updates `decision_points.status = 'resolved'`
5. **T=299.3s:** Frontend calls `resumeWargame()` (POST)
6. **T=299.4s:** Frontend sets `phase="confirmation"` (UI updated)
7. **T=300s:** Backend TTL expires, calls `_auto_complete_latest_decision()`
8. **T=300.1s:** Backend tries to update decision point:
   ```python
   UPDATE decision_points SET status = 'resolved' WHERE id = $4 AND status = 'pending'
   ```
   - **Result:** 0 rows updated (already resolved at T=299.2s)
9. **T=300.2s:** Backend checks update result:
   ```python
   if not str(update_result).endswith("1"):  # ← TRUE (0 rows)
       status = await conn.fetchval(...)
       if status != "resolved":  # ← FALSE (it IS resolved)
           return None  # ← RETURNS NONE
   ```
10. **T=300.3s:** Backend **does NOT emit** `decision_auto_completed` SSE
11. **T=300.4s:** Backend calls `_continue_wargame()` with `previous_decision_outcome=None`
    - **Problem:** Debrief/confirmation view won't show auto-complete message

### Code Reference

**Backend (simulation_orchestrator.py:740-746)** - Silent failure if already resolved
```python
if not str(update_result).endswith("1"):
    status = await conn.fetchval(
        "SELECT status FROM decision_points WHERE id = $1",
        pending_dp_id,
    )
    if status != "resolved":
        return None  # ← NO EVENT EMITTED
```

**Frontend (WarRoom.tsx:220-226)** - Confirmation overlay doesn't show auto-complete
```typescript
{wargame.state.phase === "confirmation" && !wargame.isComplete && (
  <RoundProgressOverlay
    round={wargame.state.round}
    totalRounds={totalRounds}
    tension={wargame.state.tension}
  />
)}
// ❌ NO INDICATION THAT DECISION WAS AUTO-COMPLETED
```

---

## Race Condition #3: Polling Timeout Stops Before Backend Completes

### Scenario
User resolves decision, but backend is slow to emit `simulation_complete` event.

### Code Path

**Frontend (WarRoom.tsx:123-133)**
```typescript
if (!wargame.isConnected) {
  resumePollRef.current = setInterval(() => {
    wargame.refreshState().catch(() => {});
  }, 3000);
  setTimeout(() => {
    if (resumePollRef.current) {
      clearInterval(resumePollRef.current);  // ← STOP POLLING
      resumePollRef.current = null;
    }
  }, 120_000);  // ← HARD STOP AFTER 2 MINUTES
}
```

**Backend (simulation_orchestrator.py:913-923)**
```python
try:
    await self._continue_wargame(
        scenario_id,
        result_id,
        simulation_params,
        previous_decision_outcome=auto_outcome,
        skip_cancel_heartbeat=True,
    )
except Exception:
    logger.exception("[%s] TTL auto-continue failed", scenario_id)
    await self._update_status(scenario_id, result_id, "failed")
```

### Failure Mode: **Incomplete Simulation**

1. **T=0s:** User resolves decision, polling starts (3s interval, 120s max)
2. **T=3s:** Poll #1 → `phase="confirmation"`, `isComplete=false`
3. **T=6s:** Poll #2 → `phase="confirmation"`, `isComplete=false`
4. **T=...:** Backend is running `_continue_wargame()` (slow MiroFish API)
5. **T=120s:** Frontend **stops polling** (hard timeout)
6. **T=125s:** Backend finally emits `simulation_complete` SSE
   - **Problem:** Frontend is no longer polling, SSE is dead
   - **Result:** Frontend never receives completion event
7. **T=125+:** User sees frozen "라운드 진행 중" overlay indefinitely

### Code Reference

**Frontend (WarRoom.tsx:127-132)** - Hard 2-minute timeout
```typescript
setTimeout(() => {
  if (resumePollRef.current) {
    clearInterval(resumePollRef.current);
    resumePollRef.current = null;
  }
}, 120_000);  // ← HARD STOP, NO FALLBACK
```

**Backend (simulation_orchestrator.py:1089-1099)** - Heartbeat task can take minutes
```python
heartbeat_task = asyncio.create_task(
    self._start_heartbeat_loop(
        scenario_id,
        result_id,
        mf_simulation_id,
        simulation_params,
        total_rounds,
        round_num,
    )
)
# ← This task runs for TTL duration (default: 10 minutes)
# Then calls _continue_wargame() which can take 5+ minutes
```

---

## Race Condition #4: Decision History Duplication

### Scenario
Both `decision_resolved` and `decision_auto_completed` events fire for the same decision.

### Code Path

**Frontend (useWargame.ts:312-327)**
```typescript
case "decision_resolved": {
  const resolvedLabel = data.label ?? "결정";
  const resolvedOutcome = data.outcome ?? "결정 반영됨";
  const resolvedRound = data.round ?? 0;
  setState((prev) => ({
    ...prev,
    phase: "confirmation",
    decisionPoint: null,
  }));
  setDecisionHistory((prev) => {
    const effectiveRound = resolvedRound || prev.length + 1;
    if (prev.some((d) => d.round === effectiveRound)) return prev;  // ← DEDUP CHECK
    return [...prev, { round: effectiveRound, label: resolvedLabel, outcome: resolvedOutcome }];
  });
  break;
}

case "decision_auto_completed": {
  const resolvedRound = data.round ?? 0;
  setDecisionHistory((prev) => {
    const effectiveRound = resolvedRound || prev.length + 1;
    if (prev.some((d) => d.round === effectiveRound)) return prev;  // ← DEDUP CHECK
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
}
```

### Failure Mode: **Duplicate Decision Records**

1. **T=0s:** Decision point created, round=5
2. **T=299s:** User resolves decision
3. **T=299.1s:** Backend emits `decision_resolved` SSE
4. **T=299.2s:** Frontend receives event:
   - `decisionHistory = [{round: 5, label: "군사 대응", outcome: "결정 반영됨"}]`
5. **T=300s:** Backend TTL expires
6. **T=300.1s:** Backend tries to auto-complete (already resolved)
7. **T=300.2s:** Backend **still emits** `decision_auto_completed` SSE (if code path differs)
8. **T=300.3s:** Frontend receives event:
   - Dedup check: `prev.some((d) => d.round === 5)` → **TRUE**
   - **Result:** No duplicate added (dedup works)

**BUT:** If backend emits both events in quick succession **before** frontend processes first:
- Event queue: `[decision_resolved, decision_auto_completed]`
- Frontend processes `decision_resolved` → adds to history
- Frontend processes `decision_auto_completed` → dedup check passes
- **Result:** Only one record (correct)

**However:** If events arrive out of order or with different round numbers:
- `decision_resolved` has `round=5`
- `decision_auto_completed` has `round=null` (defaults to `prev.length + 1 = 6`)
- **Result:** Two records added (incorrect)

### Code Reference

**Backend (simulation_orchestrator.py:759-770)** - Auto-complete event includes round
```python
await self._emit_sse(
    scenario_id,
    "decision_auto_completed",
    {
        "decision_point_id": pending_dp_id,
        "selected": selected_option_id,
        "outcome": outcome,
        "reason": "idle_ttl_expired",
        "round": int(snapshot.get("round_number") or 0),  # ← INCLUDES ROUND
    },
)
```

**Frontend (useWargame.ts:329-344)** - Dedup relies on round number
```typescript
case "decision_auto_completed": {
  const resolvedRound = data.round ?? 0;  // ← IF 0, DEFAULTS TO prev.length + 1
  setDecisionHistory((prev) => {
    const effectiveRound = resolvedRound || prev.length + 1;  // ← FALLBACK
    if (prev.some((d) => d.round === effectiveRound)) return prev;
    // ...
  });
}
```

---

## Race Condition #5: Phase Desync During Auto-Continue

### Scenario
Backend auto-completes decision and calls `_continue_wargame()`, but frontend is still in `confirmation` phase.

### Code Path

**Backend (simulation_orchestrator.py:904-912)**
```python
await self._emit_sse(
    scenario_id,
    "phase_change",
    {
        "phase": "simulation",
        "round": current_round + 1,
        "status": "idle_timeout_auto_continue",
    },
)
```

**Frontend (useWargame.ts:263-273)**
```typescript
case "phase_change":
  setState((prev) => ({
    ...prev,
    phase: data.phase as WargamePhase,
    round: data.round ?? prev.round,
    tension: data.tension ?? prev.tension,
    // FIX: phase_change arrives before decision_required — clear stale data to prevent flash
    ...(data.phase === "briefing" || data.phase === "simulation"
      ? { briefing: null, decisionPoint: null }
      : {}),
  }));
  break;
```

### Failure Mode: **Stale Briefing/Decision Card**

1. **T=0s:** User in `decision` phase, sees decision card
2. **T=300s:** Backend TTL expires
3. **T=300.1s:** Backend emits `decision_auto_completed` SSE
4. **T=300.2s:** Backend emits `phase_change` SSE with `phase="simulation"`
5. **T=300.3s:** Frontend receives `decision_auto_completed` event
   - Updates `decisionHistory`
   - **Does NOT clear** `state.decisionPoint`
6. **T=300.4s:** Frontend receives `phase_change` event
   - Sets `phase="simulation"`
   - Clears `decisionPoint` (line 271)
7. **T=300.5s:** Frontend renders
   - **Expected:** No decision card (phase=simulation, decisionPoint=null)
   - **Actual:** Correct (phase_change clears it)

**BUT:** If events arrive out of order:
1. **T=300.3s:** Frontend receives `phase_change` first
   - Sets `phase="simulation"`, clears `decisionPoint`
2. **T=300.4s:** Frontend receives `decision_auto_completed`
   - Tries to update `decisionHistory` with `data.round`
   - **Problem:** If `data.round` is wrong, dedup fails

### Code Reference

**Frontend (useWargame.ts:269-272)** - Phase change clears stale decision point
```typescript
...(data.phase === "briefing" || data.phase === "simulation"
  ? { briefing: null, decisionPoint: null }
  : {}),
```

---

## Summary of Failure Modes

| # | Condition | Trigger | Symptom | Impact |
|---|-----------|---------|---------|--------|
| 1 | SSE drops before TTL | Network error | Polling returns stale decision point | User sees frozen decision card |
| 2 | User resolves just as TTL expires | Race condition | Auto-complete event not emitted | Debrief doesn't show auto-complete message |
| 3 | Polling timeout before backend completes | 120s hard limit | Frontend stops polling before simulation_complete | User sees frozen progress overlay |
| 4 | Both decision_resolved and decision_auto_completed fire | Event ordering | Duplicate decision history entries | Debrief shows duplicate decisions |
| 5 | Phase change arrives before decision_auto_completed | Event ordering | Stale decision point in UI | Decision card flashes then disappears |

---

## Recommended Fixes

### Fix #1: Extend Polling Timeout
**File:** `frontend/src/components/wargame/WarRoom.tsx:127-132`

```typescript
// Current: 120_000ms (2 minutes)
// Recommended: 600_000ms (10 minutes) or dynamic based on TTL
setTimeout(() => {
  if (resumePollRef.current) {
    clearInterval(resumePollRef.current);
    resumePollRef.current = null;
  }
}, 600_000);  // ← INCREASE TO 10 MINUTES
```

### Fix #2: Emit Auto-Complete Event Even If Already Resolved
**File:** `backend/app/services/simulation_orchestrator.py:740-770`

```python
# Current: Returns None if already resolved
# Recommended: Always emit event for frontend awareness
if not str(update_result).endswith("1"):
    status = await conn.fetchval(
        "SELECT status FROM decision_points WHERE id = $1",
        pending_dp_id,
    )
    if status == "resolved":
        # ← STILL EMIT EVENT (decision was resolved by user)
        await self._emit_sse(
            scenario_id,
            "decision_auto_completed",
            {
                "decision_point_id": pending_dp_id,
                "selected": selected_option_id,
                "outcome": "사용자가 이미 결정했습니다.",
                "reason": "user_resolved_before_ttl",
                "round": int(snapshot.get("round_number") or 0),
            },
        )
        return outcome
    else:
        return None
```

### Fix #3: Ensure Round Number in Auto-Complete Event
**File:** `backend/app/services/simulation_orchestrator.py:767`

```python
# Current: Uses snapshot.get("round_number") which might be None
# Recommended: Fetch from decision_points table
round_num = dp_row.get("round_number") or int(snapshot.get("round_number") or 0)
await self._emit_sse(
    scenario_id,
    "decision_auto_completed",
    {
        "decision_point_id": pending_dp_id,
        "selected": selected_option_id,
        "outcome": outcome,
        "reason": "idle_ttl_expired",
        "round": round_num,  # ← ENSURE NOT NULL
    },
)
```

### Fix #4: Add Confirmation Message for Auto-Complete
**File:** `frontend/src/components/wargame/WarRoom.tsx:220-226`

```typescript
{wargame.state.phase === "confirmation" && !wargame.isComplete && (
  <RoundProgressOverlay
    round={wargame.state.round}
    totalRounds={totalRounds}
    tension={wargame.state.tension}
    autoCompleted={wargame.decisionHistory.some(d => d.outcome.includes("TTL"))}  // ← ADD
  />
)}
```

### Fix #5: Implement Exponential Backoff for Polling Timeout
**File:** `frontend/src/components/wargame/WarRoom.tsx:96-134`

```typescript
const handleDecisionConfirm = async (selectedOptionId: string) => {
  // ... existing code ...
  
  if (!wargame.isConnected) {
    const maxWaitTime = 600_000;  // 10 minutes
    const startTime = Date.now();
    
    resumePollRef.current = setInterval(() => {
      if (Date.now() - startTime > maxWaitTime) {
        clearInterval(resumePollRef.current);
        resumePollRef.current = null;
        // ← SHOW ERROR: "Simulation taking too long"
        return;
      }
      wargame.refreshState().catch(() => {});
    }, 3000);
  }
};
```

---

## Testing Recommendations

1. **Test SSE Disconnect During Decision Wait**
   - Start wargame, reach decision point
   - Kill SSE connection (DevTools → Network → Offline)
   - Wait for polling fallback
   - Verify decision point is not duplicated in history

2. **Test TTL Expiry with Manual Resolution**
   - Start wargame, reach decision point
   - Wait 299 seconds
   - Click "결정 확정" at T=299.5s
   - Verify no duplicate decision history entries

3. **Test Polling Timeout**
   - Start wargame, reach decision point
   - Kill SSE connection
   - Resolve decision
   - Wait 120+ seconds
   - Verify simulation completes (or shows error)

4. **Test Event Ordering**
   - Inject artificial delays in backend SSE emission
   - Verify frontend handles out-of-order events correctly

---

## References

- **Frontend Hook:** `/home/swlee/osint-simulator/frontend/src/hooks/useWargame.ts`
  - Lines 14-17: Timeout constants
  - Lines 257-382: SSE event handler
  - Lines 384-409: Polling fallback
  - Lines 411-428: Heartbeat timer reset

- **Frontend Component:** `/home/swlee/osint-simulator/frontend/src/components/wargame/WarRoom.tsx`
  - Lines 96-134: Decision confirmation handler
  - Lines 220-226: Confirmation overlay

- **Backend Orchestrator:** `/home/swlee/osint-simulator/backend/app/services/simulation_orchestrator.py`
  - Lines 690-770: Auto-complete decision logic
  - Lines 808-923: Heartbeat loop and TTL handling
  - Lines 925-1099: Wargame round loop

- **Backend Router:** `/home/swlee/osint-simulator/backend/app/routers/simulation_run.py`
  - Lines 500-582: `get_wargame_status` endpoint
  - Lines 294-344: `continue_pipeline` endpoint

