# 작업 요약

## 사용자 프롬프트
1. TASK: Implement the remaining backend/external v11 gaps: TTL auto-complete semantics, previous_decision_outcome plumbing, meaningful env_constraints generation, and any safe heartbeat/control cleanup consistent with current architecture.
2. EXPECTED OUTCOME: Concrete code changes in backend/app and external/mirofish-backend that move the repo closer to spec-complete, plus a concise list of changed files and validation commands run.
3. REQUIRED TOOLS: read, grep, glob, lsp diagnostics, apply_patch, bash for py_compile/targeted validation only.
4. MUST DO: Keep changes surgical. Preserve current HTTP round-control architecture. Implement auto-complete on TTL expiry using persisted state rather than leaving run crashed. Populate previous_decision_outcome into briefings. Add real backend-side env_constraints generation where reasonable from existing decision/event data. Improve stdout/stderr cleanliness only where low-risk.
5. MUST NOT DO: Do not edit frontend files. Do not commit. Do not use type-suppression hacks. Do not redesign the whole system.

## 변경 파일
- `backend/app/services/simulation_orchestrator.py`
- `backend/app/services/context_injection.py`
- `external/mirofish-backend/app/services/simulation_runner.py`

## 주요 변경 내용
- 워게임 idle TTL 만료 시 `crashed` 처리 대신, 최신 persisted snapshot/decision_point를 기반으로 권장안 자동 확정(`decision_points.status='resolved'`) 후 이어서 라운드 재개하도록 구현.
- TTL 자동 확정 이벤트를 액션 로그(`wargame.decision_auto_completed`)와 SSE(`decision_auto_completed`)로 노출.
- `_continue_wargame`/`_run_wargame_round_loop`에 `previous_decision_outcome` 전달 경로를 추가하여 이후 briefing payload에 실제 이전 결정 결과를 포함.
- `build_inject_context`에서 이벤트/결정 데이터를 바탕으로 `env_constraints`를 생성하도록 확장:
  - 사용자 결정(비 `do_nothing`) 시 해당 행위자의 `do_nothing` 1라운드 제한
  - 고긴장 군사 이벤트/제재·무역제한 이벤트 시 소스 행위자의 `do_nothing` 1라운드 제한
- 라운드 제어 자원 정리 시 subprocess `stdin/stdout` 핸들을 안전하게 close 하도록 정리(저위험 stdout/stderr 관련 cleanup).

## 검증 커맨드
- `python -m py_compile "backend/app/services/simulation_orchestrator.py" "backend/app/services/context_injection.py" "external/mirofish-backend/app/services/simulation_runner.py"`
- `python -m py_compile "backend/app/services/simulation_orchestrator.py"`

## 진단 확인
- LSP diagnostics: 변경 파일 3개 모두 `No diagnostics found` 확인.
