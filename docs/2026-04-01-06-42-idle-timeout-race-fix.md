# Idle timeout race fix

## User prompt

> 문제 발생 사용자가 응답을 오랫동안 안하고 있으면 문제가 생긴다야
>
> 고고고ㄱ

## Summary

- Fixed the wargame idle-timeout race where TTL auto-complete and manual resume could both enter the continue path.
- Added decision-point consumption and per-result single-flight locking in the backend resume path.
- Hardened frontend state merge so stale briefing/decision UI is cleared once backend phase leaves decision flow.

## Changed files

- `backend/app/services/simulation_orchestrator.py`
- `backend/app/routers/simulation_run.py`
- `frontend/src/hooks/useWargame.ts`

## Backend changes

- Added `_wargame_continue_locks` keyed by `result_id`.
- Added `_consume_pending_snapshot_decision()` to atomically clear the snapshot's `pending_decision_point_id` before continuing.
- Extended `_continue_wargame()` / `continue_wargame()` with `expected_decision_point_id`.
- TTL auto-continue and manual continue now both target the exact resolved decision point and skip if that decision was already consumed.

## Frontend changes

- Added `mergeBackendState()` so `briefing` / `decisionPoint` are cleared automatically when backend phase is no longer `briefing` or `decision`.
- On `decision_auto_completed`, the client now immediately clears the active decision UI and moves to `confirmation` until the next phase update arrives.

## Validation

- `python -m py_compile backend/app/services/simulation_orchestrator.py backend/app/routers/simulation_run.py`
- `npx tsc --noEmit` (in `frontend/`)

## Notes

- This is a minimal race fix. It prevents duplicate continue execution for the same paused decision point without changing the broader wargame pause model.
