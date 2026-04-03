# 작업 요약: wargame loop HTTP round control 전환

## 사용자 프롬프트

```text
## TASK: Implement HTTP-based round control for wargame loop

The v11 wargame loop uses subprocess IPC (stdin/stdout) between Gateway and MiroFish, but they run in separate Docker containers. We need to add HTTP endpoints to MiroFish that proxy to the subprocess's stdin/stdout, and modify Gateway's orchestrator to call these HTTP endpoints.

## EXPECTED OUTCOME
1. MiroFish gets 3 new API endpoints for round control
2. MiroFish SimulationRunner gets methods to manage round-controlled subprocesses with stdin/stdout pipes
3. Gateway MiroFishClient gets 3 new methods
4. Gateway SimulationOrchestrator's wargame methods use HTTP instead of subprocess IPC
5. The wargame pipeline works end-to-end across Docker containers

## REQUIRED TOOLS
Edit, Read, Grep, Bash (for testing), LSP diagnostics

## MUST DO
- Part 1: external/mirofish-backend/app/services/simulation_runner.py 변경
- Part 2: external/mirofish-backend/app/api/simulation.py 엔드포인트 추가
- Part 3: backend/app/clients/mirofish.py 클라이언트 메서드 추가
- Part 4: backend/app/services/simulation_orchestrator.py 를 subprocess IPC → HTTP 호출로 변경

## MUST NOT DO
- RoundControlCoordinator(run_parallel_simulation.py) 변경 금지
- frontend / docker-compose / DB schema / 신규 dependency 변경 금지
```

## 변경 내용

### 1) MiroFish `SimulationRunner` round-control 메서드 추가
- 파일: `external/mirofish-backend/app/services/simulation_runner.py`
- 추가:
  - 클래스 변수
    - `_rc_processes: Dict[str, subprocess.Popen]`
    - `_rc_locks: Dict[str, threading.Lock]`
  - 메서드
    - `start_round_controlled(...)`
    - `proceed_round(...)`
    - `stop_round_controlled(...)`
  - 내부 유틸
    - `_read_control_stdout_line(...)` (timeout 포함)
    - `_monitor_round_controlled(...)`
    - `_cleanup_round_controlled_resources(...)`
- 동작:
  - `simulation_config.json`에 `round_control_enabled=true` 설정 후 저장
  - subprocess를 `stdin/stdout=PIPE`, `stderr=simulation.log`로 실행
  - stdout 첫 줄 `ready` NDJSON 수신/파싱 후 반환
  - `proceed` 시 stdin에 NDJSON 전송 후 최대 300초 대기해 stdout 한 줄 파싱
  - `stop` 시 stop 신호 전송 + 최대 30초 wait + 리소스 정리
  - 기존 전체 cleanup 루틴에 round-control 프로세스도 포함

### 2) MiroFish API 엔드포인트 3개 추가
- 파일: `external/mirofish-backend/app/api/simulation.py`
- 추가 라우트:
  - `POST /round_control/start`
  - `POST /round_control/proceed`
  - `POST /round_control/stop`
- 각 엔드포인트는 입력 검증 후 `SimulationRunner` 신규 메서드 호출
- 응답 형식: `{"success": true, "data": ...}`

### 3) Gateway `MiroFishClient` 메서드 3개 추가
- 파일: `backend/app/clients/mirofish.py`
- 추가 메서드:
  - `start_round_control(...)` (timeout=120)
  - `proceed_round(...)` (timeout=300)
  - `stop_round_control(...)`

### 4) Gateway Orchestrator를 HTTP round-control 흐름으로 전환
- 파일: `backend/app/services/simulation_orchestrator.py`
- 변경:
  - `_wargame_paths` 제거
  - `_wargame_processes` 제거
  - `_start_wargame_process`는 이제 `mf.start_round_control(...)` 호출 후 ready signal dict 반환
  - `_send_control_signal`은 payload type별로 MiroFish HTTP 메서드 분기 호출
  - `_read_control_signal`은 passthrough 형태 유지
  - `_run_wargame_round_loop`에서 send+read 분리 제거, `proceed` 호출 결과를 직접 사용
  - `run_wargame_pipeline`/`_continue_wargame`에서 subprocess 참조 제거 및 stop HTTP 호출 사용
  - heartbeat는 subprocess health 대신 `mf.get_run_status(...)` 기반으로 단순화

## 검증

- LSP diagnostics
  - `simulation_runner.py`: 에러 없음
  - `simulation_orchestrator.py`: 에러 없음
  - `simulation.py`, `mirofish.py`: 환경 미설치 의존성(import) 경고만 존재 (`flask`, `httpx`, `tenacity`)
- 빌드/구문 검증
  - `python -m py_compile`로 변경된 4개 파일 컴파일 성공
