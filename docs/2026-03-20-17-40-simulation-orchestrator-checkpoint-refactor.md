# SimulationOrchestrator checkpoint refactor

## User prompt

```text
## TASK
Refactor `SimulationOrchestrator` in `/home/swlee/osint-simulator/backend/app/services/simulation_orchestrator.py` to support checkpoint mode (Human-in-the-Loop pipeline pause/resume).

## EXPECTED OUTCOME
- `run_pipeline()` method UNCHANGED (auto mode regression zero)
- New `run_from_checkpoint()` method that executes the next pipeline step based on current DB status
- Each step extracted into private methods for reuse between auto and checkpoint modes
- Checkpoint data (intermediate results) saved to DB at each pause point

## REQUIRED TOOLS
- Read, Edit tools for the orchestrator file
- Read tool for mirofish.py client (already at `/home/swlee/osint-simulator/backend/app/clients/mirofish.py`)

## MUST DO

### 1. Extract step methods from run_pipeline
Break the existing sequential pipeline into private step methods. Each step method:
- Takes `(scenario_id, result_id, db_path)` as params
- Returns any intermediate result data needed by the next step
- Calls `_update_status()` before starting

Step methods to create:
```python
async def _step_ontology(self, scenario_id, result_id, seed_text, db_path) -> dict:
    """Step 1: Ontology generation. Returns ontology_result with project_id."""
    
async def _step_graph_build(self, scenario_id, result_id, project_id, db_path) -> None:
    """Step 2: Graph build. Uses project_id from step 1."""

async def _step_create_prepare(self, scenario_id, result_id, project_id, db_path) -> str:
    """Step 3+4: Simulation create + prepare. Returns mf_simulation_id."""

async def _step_run_simulation(self, scenario_id, result_id, mf_simulation_id, max_rounds, db_path) -> None:
    """Step 5: Start simulation and poll until done."""

async def _step_report(self, scenario_id, result_id, mf_simulation_id, db_path) -> None:
    """Step 6: Generate report and poll until done."""
```

### 2. Rewrite run_pipeline to use step methods
The existing `run_pipeline` should call these step methods sequentially. The behavior must be IDENTICAL to the current implementation. This is critical — auto mode must not change at all.

### 3. Add run_from_checkpoint method
```python
async def run_from_checkpoint(
    self,
    scenario_id: str,
    result_id: str,
    db_path: str,
    max_rounds: int,
    edits: dict | None = None,
) -> None:
    """Execute next pipeline step from current checkpoint status.
    
    Called by POST /continue endpoint as BackgroundTask.
    Reads current status from DB, determines next step, executes it,
    then pauses at next checkpoint (saves checkpoint_data, updates status).
    
    If this is the last segment (run+report), runs to completion.
    """
```

Logic:
1. Read current status from DB (`SELECT status, checkpoint_data, mirofish_project_id, mirofish_simulation_id FROM simulation_results WHERE id = ?`)
2. Apply edits if provided (for CP1: update seed text in seeds table; for CP5: update max_rounds)
3. Based on current status, run the appropriate step(s):
   - `checkpoint:seed` → run _step_ontology → save ontology result in checkpoint_data → set status to `checkpoint:ontology`
   - `checkpoint:ontology` → run _step_graph_build → set status to `checkpoint:graph`
   - `checkpoint:graph` → run _step_create_prepare → save mf_simulation_id → set status to `checkpoint:profiles`
   - `checkpoint:profiles` → set status to `checkpoint:config` (no MiroFish call needed — just transition to config review)
   - `checkpoint:config` → run _step_run_simulation + _step_report + _collect_and_store_results → set status to `completed`
4. On failure at any point: set status to `failed`

### 4. Add checkpoint data helper methods
```python
async def _save_checkpoint_data(self, db_path, result_id, data: dict) -> None:
    """Save intermediate result JSON to checkpoint_data column."""
    
async def _get_checkpoint_info(self, db_path, result_id) -> dict:
    """Read current status, checkpoint_data, and MiroFish IDs from DB."""

async def _apply_edits(self, db_path, result_id, current_status, edits: dict) -> None:
    """Apply user edits based on checkpoint type.
    - checkpoint:seed → update seed text in seeds table
    - checkpoint:config → update max_rounds in scenarios table
    """
```

### 5. Checkpoint data to save at each pause
- After ontology step → save `{"ontology": <ontology_result_from_generate_ontology>}` to checkpoint_data
- After graph_build → save `{"step": "graph_build"}` (no rich data available from MiroFish API response)
- After create_prepare → save `{"mf_simulation_id": "..."}` to checkpoint_data
- After config_review → save `{"max_rounds": N, "platform": "twitter"}` to checkpoint_data

## MUST NOT DO
- Do NOT modify the existing `run_pipeline` method's logic/behavior. Only extract steps into private methods and have `run_pipeline` call them. The observable behavior must be identical.
- Do NOT add any new dependencies or imports beyond what's already used
- Do NOT add `as any`, `@ts-ignore`, or type suppressions
- Do NOT change the method signatures of `_update_status`, `_update_ids`, `_collect_and_store_results`
- Do NOT rename SIMULATION_REQUIREMENT or any constants
- Do NOT modify polling timeouts or intervals
- Do NOT add error handling that changes existing failure behavior

## CONTEXT
- Current file: 249 lines, see `/home/swlee/osint-simulator/backend/app/services/simulation_orchestrator.py`
- MiroFish client: see `/home/swlee/osint-simulator/backend/app/clients/mirofish.py`
- DB schema: `simulation_results` table has columns: id, scenario_id, mirofish_simulation_id, mirofish_project_id, status, platform, pipeline_mode, checkpoint_data, results, geojson, report, created_at, completed_at
- Seeds table: `seeds` has columns: id, scenario_id, text, metadata, created_at
- Scenarios table: `scenarios` has column: max_rounds
- Status values for checkpoints: "checkpoint:seed", "checkpoint:ontology", "checkpoint:graph", "checkpoint:profiles", "checkpoint:config"
- Package manager: `uv` (NOT pip). Do NOT install anything.
- No linter/formatter configured. Follow existing code style exactly.
```

## Changes made

- Extracted pipeline step methods: `_step_ontology`, `_step_graph_build`, `_step_create_prepare`, `_step_run_simulation`, `_step_report`.
- Rewrote `run_pipeline()` to call extracted step methods in the exact same order and with the same statuses/timeouts/polling behavior.
- Added checkpoint helpers: `_save_checkpoint_data`, `_get_checkpoint_info`, `_apply_edits`.
- Added `run_from_checkpoint()` with status-based transitions:
  - `checkpoint:seed` -> ontology -> save ontology checkpoint -> `checkpoint:ontology`
  - `checkpoint:ontology` -> graph build -> save graph marker -> `checkpoint:graph`
  - `checkpoint:graph` -> create+prepare -> save simulation id -> `checkpoint:profiles`
  - `checkpoint:profiles` -> save config-review payload -> `checkpoint:config`
  - `checkpoint:config` -> run + report + collect -> completed flow
- Added failure handling for checkpoint mode to set `status='failed'` on exception.

## Verification

- Ran `uv run python -m py_compile backend/app/services/simulation_orchestrator.py` (success).
- LSP diagnostics reports one environment-level import resolution issue for `aiosqlite` (`reportMissingImports`), not introduced by this refactor.
