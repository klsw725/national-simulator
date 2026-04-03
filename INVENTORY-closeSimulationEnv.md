# Inventory: `closeSimulationEnv` and Related Environment APIs

**Date:** 2026-03-31  
**Status:** Build Error - Missing Exports  
**Severity:** Critical (Frontend build blocked)

---

## Summary

The frontend component `ConversationPanel.tsx` imports and calls **three missing functions** from `@/lib/gatewayApi`:
1. `closeSimulationEnv(scenarioId)` — line 126
2. `getEnvStatus(scenarioId)` — line 39
3. `interviewAllAgents(scenarioId, prompt)` — line 79
4. `interviewAgent(scenarioId, agentId, prompt)` — line 90

These functions **do not exist** in the frontend API layer. However, the **backend MiroFish client** (`backend/app/clients/mirofish.py`) has the corresponding implementations.

---

## References Found

### Frontend (Missing Exports)

| File | Line | Function | Status |
|------|------|----------|--------|
| `frontend/src/components/simulation/ConversationPanel.tsx` | 39 | `api.getEnvStatus(scenarioId)` | ❌ Missing |
| `frontend/src/components/simulation/ConversationPanel.tsx` | 79 | `api.interviewAllAgents(scenarioId, text.trim())` | ❌ Missing |
| `frontend/src/components/simulation/ConversationPanel.tsx` | 90 | `api.interviewAgent(scenarioId, agentId, text.trim())` | ❌ Missing |
| `frontend/src/components/simulation/ConversationPanel.tsx` | 126 | `api.closeSimulationEnv(scenarioId)` | ❌ Missing |
| `frontend/src/types/simulation.ts` | 357-363 | `EnvStatus` type definition | ✅ Exists |

### Backend (Implementations Exist)

| File | Method | Signature | Status |
|------|--------|-----------|--------|
| `backend/app/clients/mirofish.py` | `get_env_status()` | `async def get_env_status(self, simulation_id: str) -> dict` (line 377) | ✅ Exists |
| `backend/app/clients/mirofish.py` | `interview_agent()` | `async def interview_agent(self, simulation_id: str, agent_id: int, prompt: str, ...)` (line 388) | ✅ Exists |
| `backend/app/clients/mirofish.py` | `interview_all_agents()` | `async def interview_all_agents(self, simulation_id: str, prompt: str, ...)` (line 412) | ✅ Exists |
| `backend/app/clients/mirofish.py` | `close_env()` | `async def close_env(self, simulation_id: str, timeout: int = ...) -> dict` (line 476) | ✅ Exists |

### Backend Gateway Routers

| Router | Endpoints | Status |
|--------|-----------|--------|
| `backend/app/routers/copilot.py` | `/api/copilot/chat` | ✅ Exists (but no env/interview endpoints) |
| `backend/app/routers/simulation_run.py` | (not checked yet) | ? |
| `backend/app/routers/simulation_live.py` | (not checked yet) | ? |

---

## Backend MiroFish Client Methods (Confirmed)

### `get_env_status(simulation_id: str) -> dict`
- **Location:** `backend/app/clients/mirofish.py:377-386`
- **Endpoint:** `POST /api/simulation/env-status`
- **Returns:** `{"env_alive": bool, "reddit_available": bool, "twitter_available": bool, "message": str}`
- **Purpose:** Check if simulation environment is active

### `interview_agent(simulation_id, agent_id, prompt, platform=None, timeout=...) -> dict`
- **Location:** `backend/app/clients/mirofish.py:388-410`
- **Endpoint:** `POST /api/simulation/interview`
- **Returns:** Agent response data
- **Purpose:** Interview a single agent

### `interview_all_agents(simulation_id, prompt, platform=None, timeout=...) -> dict`
- **Location:** `backend/app/clients/mirofish.py:412-432`
- **Endpoint:** `POST /api/simulation/interview/all`
- **Returns:** Responses from all agents
- **Purpose:** Interview all agents in parallel

### `close_env(simulation_id, timeout=...) -> dict`
- **Location:** `backend/app/clients/mirofish.py:476-486`
- **Endpoint:** `POST /api/simulation/close-env`
- **Returns:** Confirmation data
- **Purpose:** Terminate simulation environment

---

## Frontend API Layer Structure

**Current exports from `frontend/src/lib/gatewayApi.ts`:**
```typescript
export * from "./api/scenarioApi";
export * from "./api/seedApi";
export * from "./api/simulationApi";
export * from "./api/liveApi";
export * from "./api/whatifApi";
export * from "./api/briefingApi";
export * from "./api/analyticsApi";
export * from "./api/copilotApi";
export * from "./api/causalApi";
export * from "./api/geopoliticsApi";
```

**Missing module:** No `conversationApi.ts` or `interviewApi.ts` exists.

---

## Recommended Minimal Fix

### Option A: Create `frontend/src/lib/api/conversationApi.ts` (Recommended)

Create a new file with these exports:

```typescript
import type { EnvStatus, InterviewResult } from "@/types/simulation";
import { fetchJSON, JSON_HEADERS } from "./fetchUtils";

export function getEnvStatus(scenarioId: string): Promise<EnvStatus> {
  return fetchJSON(`/api/scenario/${scenarioId}/env-status`);
}

export function interviewAgent(
  scenarioId: string,
  agentId: number,
  prompt: string,
): Promise<InterviewResult> {
  return fetchJSON(`/api/scenario/${scenarioId}/interview`, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({
      agent_id: agentId,
      prompt,
    }),
  });
}

export function interviewAllAgents(
  scenarioId: string,
  prompt: string,
): Promise<{ results: InterviewResult[] }> {
  return fetchJSON(`/api/scenario/${scenarioId}/interview/all`, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ prompt }),
  });
}

export function closeSimulationEnv(scenarioId: string): Promise<{ message: string }> {
  return fetchJSON(`/api/scenario/${scenarioId}/close-env`, {
    method: "POST",
    headers: JSON_HEADERS,
  });
}
```

Then add to `frontend/src/lib/gatewayApi.ts`:
```typescript
export * from "./api/conversationApi";
```

### Option B: Add to existing `copilotApi.ts`

Less clean but faster. Add the four functions to `frontend/src/lib/api/copilotApi.ts`.

---

## Backend Gateway Router Requirements

**Status:** ❌ **ENDPOINTS DO NOT EXIST**

The gateway API **must create** these endpoints (they are not currently implemented):

| Endpoint | Method | Purpose | Router |
|----------|--------|---------|--------|
| `/api/scenario/{scenarioId}/env-status` | POST | Proxy to MiroFish `get_env_status()` | simulation_live.py (new) |
| `/api/scenario/{scenarioId}/interview` | POST | Proxy to MiroFish `interview_agent()` | simulation_live.py (new) |
| `/api/scenario/{scenarioId}/interview/all` | POST | Proxy to MiroFish `interview_all_agents()` | simulation_live.py (new) |
| `/api/scenario/{scenarioId}/close-env` | POST | Proxy to MiroFish `close_env()` | simulation_live.py (new) |

**Verified:** Checked `simulation_live.py` (320 lines) — no interview or env-status endpoints exist.  
**Verified:** Checked `simulation_run.py` — no interview or env-status endpoints exist.  
**Verified:** Checked `copilot.py` — only `/api/copilot/chat` exists.

**Action:** Add these 4 endpoints to `backend/app/routers/simulation_live.py`.

---

## Type Definitions (Already Exist)

✅ `frontend/src/types/simulation.ts:357-363` defines `EnvStatus`:
```typescript
export interface EnvStatus {
  simulation_id: string;
  env_alive: boolean;
  reddit_available: boolean;
  twitter_available: boolean;
  message: string;
}
```

✅ `frontend/src/types/simulation.ts:339-347` defines `InterviewResult`:
```typescript
export interface InterviewResult {
  agent_id: number;
  agent_name?: string;
  prompt: string;
  response?: string;
  platform?: string;
  timestamp?: string;
  platforms?: Record<string, { agent_id: number; response: string; platform: string }>;
}
```

---

## Next Steps (Priority Order)

### Phase 1: Backend (Required for frontend to work)
1. **Add 4 endpoints to `backend/app/routers/simulation_live.py`:**
   - `POST /api/scenario/{scenario_id}/env-status` → proxy `mf_client.get_env_status()`
   - `POST /api/scenario/{scenario_id}/interview` → proxy `mf_client.interview_agent()`
   - `POST /api/scenario/{scenario_id}/interview/all` → proxy `mf_client.interview_all_agents()`
   - `POST /api/scenario/{scenario_id}/close-env` → proxy `mf_client.close_env()`

### Phase 2: Frontend (Unblocks build)
2. **Create `frontend/src/lib/api/conversationApi.ts`** with the four missing functions
3. **Export from `frontend/src/lib/gatewayApi.ts`:** `export * from "./api/conversationApi";`
4. **Run frontend build** to verify no more import errors

### Phase 3: Testing
5. **Test ConversationPanel** functionality (env status polling, interview calls, close-env)

---

## Files to Modify

**Backend:**
- ✅ Edit: `backend/app/routers/simulation_live.py` (add 4 endpoints)

**Frontend:**
- ✅ Create: `frontend/src/lib/api/conversationApi.ts`
- ✅ Edit: `frontend/src/lib/gatewayApi.ts` (add export)

