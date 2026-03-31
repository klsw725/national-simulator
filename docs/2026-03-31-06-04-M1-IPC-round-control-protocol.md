# 작업 기록: M1 IPC Round Control Protocol

## 변경 요약

- 대상 파일
  - `external/mirofish-backend/scripts/run_parallel_simulation.py`
  - `external/mirofish-backend/scripts/run_twitter_simulation.py`
  - `external/mirofish-backend/scripts/run_reddit_simulation.py`

- 핵심 구현
  1. NDJSON 제어 함수 추가
     - `_send_control(msg)` (stdout NDJSON 전송)
     - `_wait_for_control_signal()` (stdin NDJSON 수신)
  2. `round_control_enabled` 설정 플래그 로드 및 적용
  3. 라운드 배리어 추가
     - `proceed` 대기 후 라운드 진행
     - `heartbeat` 수신 시 `heartbeat_ack` 즉시 응답
     - `stop` 수신 시 라운드 루프 중단
     - 라운드 완료 시 `round_complete` 전송
     - 파싱/EOF 오류 시 `error` 전송
  4. 컨텍스트 주입 스텁 추가
     - `_inject_context_to_env(...)`는 현재 로그만 남기고 실제 주입은 미구현(M2 예정)
  5. stdout/stderr 분리
     - 세 스크립트에 모듈 단위 `print` 재정의(기본 stderr)
     - `_redirect_logging_streams_to_stderr()` 추가 및 main 진입 시 적용
  6. 병렬 스크립트 라운드 동기화
     - `RoundControlCoordinator` 추가
     - Twitter/Reddit 동시 실행 시 leader/follower 배리어로 동일 라운드 proceed 동기화
     - 플랫폼별 액션을 수집해 단일 `round_complete`로 병합 송신

## 검증

- `python -m py_compile`로 수정 3개 스크립트 문법 검증 통과
  - `run_parallel_simulation.py`
  - `run_twitter_simulation.py`
  - `run_reddit_simulation.py`
- LSP diagnostics 실행함 (환경 의존 import 미해결 및 기존 타입 경고 다수 존재)

## 재현용 사용자 프롬프트

```text
1. TASK: Implement M1 — IPC Round Control Protocol for MiroFish's run_parallel_simulation.py. Add a round barrier that pauses between rounds waiting for orchestrator signals via stdin/stdout NDJSON protocol.

2. EXPECTED OUTCOME:
- `round_control_enabled` flag in simulation config
- When enabled: each round waits for `proceed` signal on stdin before executing, sends `round_complete` with actions on stdout after
- When disabled: existing behavior unchanged (zero regression)
- All logging redirected to stderr, stdout reserved for control messages only
- NDJSON protocol with 7 message types: ready, proceed, round_complete, stop, error, heartbeat, heartbeat_ack

3. REQUIRED TOOLS: Read, Edit, Write, Bash, Grep, Glob, LSP tools

4. MUST DO:

**Step 0: Read the existing code thoroughly before making ANY changes**
- Read `external/mirofish-backend/scripts/run_parallel_simulation.py` FULLY
- Read `external/mirofish-backend/scripts/run_twitter_simulation.py` FULLY
- Read `external/mirofish-backend/scripts/run_reddit_simulation.py` FULLY
- Understand the existing round loop structure, `_shutdown_event`, action logging, IPC handler
- Read the simulation config loading to understand where to add `round_control_enabled`

**Step 1: Add control message functions**

Add these functions to `run_parallel_simulation.py`:

import json
import sys

def _send_control(msg: dict) -> None:
    """Send NDJSON control message to stdout. Logs go to stderr."""
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stdout.flush()

async def _wait_for_control_signal() -> dict:
    """Wait for NDJSON control message from stdin."""
    loop = asyncio.get_event_loop()
    line = await loop.run_in_executor(None, sys.stdin.readline)
    if not line:
        raise EOFError("stdin closed")
    return json.loads(line.strip())

**Step 2: Redirect all logging to stderr**

Find where logging is configured in the simulation scripts and ensure:
- All `logging.StreamHandler()` instances use `sys.stderr`
- All `print()` statements are converted to `logger.info()` or use `file=sys.stderr`
- The `main_logger` and any other loggers in the scripts output to stderr
- Check OASIS and LiteLLM library logging — redirect if they write to stdout

**Step 3: Add round barrier to the main simulation loop**

In `run_parallel_simulation.py`, find the main round loop (the `for round_num in range(total_rounds):` loop) and add the round barrier:

# At the start, after environment initialization:
if round_control_enabled:
    _send_control({
        "type": "ready",
        "run_id": run_id,
        "total_rounds": total_rounds,
        "platforms": list(platform_configs.keys()),
    })

# Inside the round loop, BEFORE existing round execution:
if round_control_enabled:
    try:
        signal = await _wait_for_control_signal()
        if signal.get("type") == "stop":
            if main_logger:
                main_logger.info(f"Received stop signal: {signal.get('reason', 'unknown')}")
            break
        if signal.get("type") == "proceed":
            if "inject_context" in signal:
                await _inject_context_to_env(envs, signal["inject_context"])
        elif signal.get("type") == "heartbeat":
            _send_control({"type": "heartbeat_ack", "timestamp": signal.get("timestamp", "")})
            continue  # Don't advance round on heartbeat
    except (json.JSONDecodeError, EOFError) as e:
        _send_control({"type": "error", "round": round_num + 1, "message": str(e), "recoverable": False})
        break

# After round execution completes (after action logging):
if round_control_enabled:
    _send_control({
        "type": "round_complete",
        "round": round_num + 1,
        "actions": actual_actions,  # The actions collected this round
        "stats": {
            "twitter_actions": twitter_action_count,
            "reddit_actions": reddit_action_count,
            "active_agents": len(active_agents),
        },
    })

**Step 4: Add `_inject_context_to_env` stub**

async def _inject_context_to_env(envs: dict, context: dict) -> None:
    """Inject system posts into OASIS environments.
    Stub for M2 — logs received context for now."""
    if main_logger:
        posts = context.get("system_posts", [])
        main_logger.info(f"[round_control] Received {len(posts)} system posts for injection (stub)")
    # M2 will implement actual OASIS environment injection

**Step 5: Load `round_control_enabled` from config**

Find where `simulation_config.json` is loaded and add:
round_control_enabled = config.get("round_control_enabled", False)

**Step 6: Handle the Twitter and Reddit individual simulation scripts**

The `run_twitter_simulation.py` and `run_reddit_simulation.py` may have their own round loops. Check if they're used independently or only through `run_parallel_simulation.py`. If they have independent round loops:
- Add the same round barrier pattern
- BUT: only if they can be run standalone with round control. If they're always called through the parallel script, leave them as-is.

**Step 7: Verify**
- Check there are no remaining `print()` calls that go to stdout
- Run LSP diagnostics on modified files
- Verify the control flow: when `round_control_enabled=False`, no IPC code runs at all

5. MUST NOT DO:
- Do NOT modify any backend/app/ files — this is MiroFish only
- Do NOT change the simulation logic (env.step, action logging, agent scheduling)
- Do NOT add new dependencies to MiroFish
- Do NOT create commits
- Do NOT modify the OASIS framework code
- Do NOT implement actual context injection (that's M2) — just add the stub
- Do NOT break the existing non-round-control flow. The flag defaults to False.
- Do NOT use `as any`, `@ts-ignore`, or suppress type errors

6. CONTEXT:
- Working directory: /home/swlee/osint-simulator
- MiroFish simulation scripts are in external/mirofish-backend/scripts/
- The main simulation is run_parallel_simulation.py which coordinates Twitter + Reddit platforms
- The existing IPC handler (ParallelIPCHandler) uses stdin/stdout for interview commands — study this pattern
- AGENTS.md says: MiroFish uses pip + requirements.txt (not uv). Don't confuse tooling.
- The simulation is spawned as a subprocess by SimulationRunner in external/mirofish-backend/app/services/simulation_runner.py
- Read the PRD at docs/specs/v11-wargame-loop/prds/v11-backend-wargame-engine.md for full M1 spec
```
