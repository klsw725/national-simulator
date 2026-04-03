# Idle timeout repro UI

## User prompt

> 그려

## Summary

- Added a configurable wargame idle TTL field to the scenario form advanced settings.
- Added a one-click `재현용 1분` helper button for fast idle-timeout race reproduction.

## Changed files

- `frontend/src/components/simulation/ScenarioForm.tsx`
- `frontend/src/types/simulation.ts`

## Details

- Exposed `wargame_idle_ttl_minutes` in the frontend simulation param types.
- Scenario creation now sends the selected TTL value to the backend.
- The advanced settings panel now includes:
  - numeric TTL input (`1` to `120` minutes)
  - quick preset button for `1` minute
  - short helper text explaining the repro use case

## Validation

- `npx tsc --noEmit` (in `frontend/`)
