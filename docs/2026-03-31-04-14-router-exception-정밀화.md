# 작업 요약

- backend 라우터 6개 파일에서 광범위한 `except Exception`을 요청된 예외 타입으로 축소했습니다.
- fallback 반환 경로 중 무로그 구간(`simulation_live.py` 3곳, `simulation_interactive.py` 1곳)에 `logger.warning(..., %s)`를 추가했습니다.
- 각 대상 파일에 `httpx` import가 없던 경우 추가했습니다.
- 검증: `backend` 디렉터리에서 `uv run python -c "from app.main import app; print('OK')"` 실행 결과 `OK` 확인.

## 수정 파일

- `backend/app/routers/seed.py`
- `backend/app/routers/briefing.py`
- `backend/app/routers/simulation_live.py`
- `backend/app/routers/simulation_interactive.py`
- `backend/app/routers/copilot.py`
- `backend/app/routers/causal.py`

## 사용자 프롬프트

```text
## TASK
Replace overly broad `except Exception` blocks in backend router files with specific exception types, and add logging where it's missing.

## EXPECTED OUTCOME
All modified router files have specific exception types instead of bare `except Exception`, with proper logging. Server still starts correctly.

## REQUIRED TOOLS
- Read tool (to read each file's except blocks in context)
- Edit tool (to fix each except block)
- Bash tool (to verify: `cd backend && uv run python -c "from app.main import app; print('OK')"`)

## MUST DO

### Rules for replacement:
1. **MiroFish proxy calls** (calling `mf_client.*`): Use `except (httpx.HTTPError, RuntimeError, TimeoutError) as e`
   - Add `import httpx` at the top of the file if not present
2. **ShadowBroker proxy calls** (calling `sb_client.*`): Use `except httpx.HTTPError as e`
3. **Seed/Briefing generation calls**: Use `except (httpx.HTTPError, ValueError) as e`
4. **JSON parsing failures**: Use `except (json.JSONDecodeError, KeyError, ValueError) as e`
5. **Background task exceptions** (in `_generate_decision_options`): Keep `except Exception as exc` — background tasks must not crash

### Where `except Exception` already logs properly:
If the block already has `logger.exception(...)` followed by `raise HTTPException(...)`, that's acceptable. Just make the exception type more specific per rules above.

### Where `except Exception` silently drops errors:
These are the most critical to fix. Add `logger.warning(...)` with the exception.

### Files to fix:

**1. `/home/swlee/osint-simulator/backend/app/routers/seed.py`** (3 instances)
- Read lines around 69, 157, 225
- These wrap SeedGenerator calls → `except (httpx.HTTPError, ValueError) as e`
- They already have `logger.exception()` — just narrow the exception type

**2. `/home/swlee/osint-simulator/backend/app/routers/briefing.py`** (1 instance)
- Read line around 39
- Wraps BriefingGenerator call → `except (httpx.HTTPError, ValueError) as e`
- Already has `logger.exception()` — just narrow the type
- Note: there's also `except ValueError as exc` before it — keep that separate

**3. `/home/swlee/osint-simulator/backend/app/routers/simulation_live.py`** (6 instances)
- Read lines around 31, 58, 78, 98, 119, 138
- Lines 31, 119, 138: Return fallback data **without logging** — ADD `logger.warning("...: %s", e)` 
- Lines 58, 78, 98: Already have `logger.exception()` + `raise HTTPException` — narrow type
- All are MiroFish proxy calls → `except (httpx.HTTPError, RuntimeError, TimeoutError) as e`

**4. `/home/swlee/osint-simulator/backend/app/routers/simulation_interactive.py`** (6 instances)
- Read lines around 377, 404, 431, 458, 479, 499
- Line 377: Returns fallback **without logging** — ADD `logger.warning()`
- Lines 404, 431, 458, 479, 499: MiroFish proxy calls, already have logging
- All → `except (httpx.HTTPError, RuntimeError, TimeoutError) as e`

**5. `/home/swlee/osint-simulator/backend/app/routers/copilot.py`** (1 instance)
- Read line around 38
- Wraps copilot service call → `except (httpx.HTTPError, ValueError) as e`

**6. `/home/swlee/osint-simulator/backend/app/routers/causal.py`** (3 instances)
- Read lines around 285, 339, 388
- These wrap causal analysis calls → `except (httpx.HTTPError, ValueError) as e`

### Import additions:
Add `import httpx` at the top of each file that doesn't already have it (all router files above).

### DO NOT TOUCH:
- `main.py` — health checks are intentionally broad
- `simulation_run.py` — `_generate_decision_options` background task is intentionally broad
- `simulation_run.py` line 118 — the seed generation `except Exception` with `logger.exception` — narrow to `except (httpx.HTTPError, ValueError)`
- But DO fix `simulation_run.py` line 101 — background task function, keep as `except Exception`

## MUST NOT DO
- Do NOT change any business logic
- Do NOT modify error messages shown to users
- Do NOT add new error response formats
- Do NOT change HTTP status codes
- Do NOT remove any existing logging

## CONTEXT
- MiroFish client raises: `httpx.TimeoutException`, `httpx.ConnectError`, `httpx.HTTPStatusError`, `RuntimeError`, `TimeoutError`
- ShadowBroker client raises: `httpx.TimeoutException`, `httpx.ConnectError`, `httpx.HTTPStatusError`
- SeedGenerator/BriefingGenerator can raise: any of the above + `ValueError`, `KeyError`, `json.JSONDecodeError` from LLM response parsing
- AGENTS.md: LLM은 OpenAI Compatible API — do NOT import openai-specific exceptions
```
