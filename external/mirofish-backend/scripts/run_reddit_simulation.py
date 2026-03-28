"""
OASIS Reddit 시뮬레이션 프리셋 스크립트
이 스크립트는 설정 파일의 파라미터를 읽어 시뮬레이션을 실행하며, 전 과정을 자동화합니다.

기능 및 특징:
- 시뮬레이션 완료 후 환경을 즉시 종료하지 않고 명령 대기 모드로 진입
- IPC를 통한 인터뷰(Interview) 명령 수신 지원
- 개별 에이전트 인터뷰 및 일괄 인터뷰 지원
- 원격 환경 종료 명령 지원

사용 방법:
    python run_reddit_simulation.py --config /path/to/simulation_config.json
    python run_reddit_simulation.py --config /path/to/simulation_config.json --no-wait  # 완료 후 즉시 종료
"""

import argparse
import asyncio
import json
import logging
import os
import random
import signal
import sys
import sqlite3
from datetime import datetime
from typing import Dict, Any, List, Optional

# 전역 변수: 시그널 처리용
_shutdown_event = None
_cleanup_done = False

# 프로젝트 경로 추가
_scripts_dir = os.path.dirname(os.path.abspath(__file__))
_backend_dir = os.path.abspath(os.path.join(_scripts_dir, ".."))
_project_root = os.path.abspath(os.path.join(_backend_dir, ".."))
sys.path.insert(0, _scripts_dir)
sys.path.insert(0, _backend_dir)

# 프로젝트 루트 디렉토리의 .env 파일 로드 (LLM_API_KEY 등 설정 포함)
from dotenv import load_dotenv

_env_file = os.path.join(_project_root, ".env")
if os.path.exists(_env_file):
    load_dotenv(_env_file)
else:
    _backend_env = os.path.join(_backend_dir, ".env")
    if os.path.exists(_backend_env):
        load_dotenv(_backend_env)


import re

from action_logger import PlatformActionLogger


def _patch_openai_thinking_mode():
    """CAMEL OpenAIModel의 LLM 호출을 감싸서 content=None일 때 reasoning으로 대체."""
    try:
        from camel.models.openai_model import OpenAIModel

        _orig_sync = OpenAIModel._request_chat_completion
        _orig_async = OpenAIModel._arequest_chat_completion

        _call_count = [0]

        def _fix_content(response):
            _call_count[0] += 1
            for choice in response.choices:
                was_none = choice.message.content is None
                if was_none:
                    extra = getattr(choice.message, "model_extra", None) or {}
                    rc = extra.get("reasoning_content") or extra.get("reasoning")
                    if rc:
                        object.__setattr__(choice.message, "content", rc)
                        print(f"[THINKING-PATCH] call#{_call_count[0]}: content was None, replaced with reasoning ({len(rc)} chars)", flush=True)
                    else:
                        print(f"[THINKING-PATCH] call#{_call_count[0]}: content was None, NO reasoning found. extra keys={list(extra.keys())}", flush=True)
                else:
                    print(f"[THINKING-PATCH] call#{_call_count[0]}: content OK ({len(choice.message.content)} chars)", flush=True)
            return response

        def _patched_sync(self, *a, **kw):
            return _fix_content(_orig_sync(self, *a, **kw))

        async def _patched_async(self, *a, **kw):
            return _fix_content(await _orig_async(self, *a, **kw))

        OpenAIModel._request_chat_completion = _patched_sync
        OpenAIModel._arequest_chat_completion = _patched_async
    except Exception:
        pass


def _install_stuck_debugger():
    import faulthandler, signal, threading

    faulthandler.enable()

    def _dump_on_alarm(signum, frame):
        import sys, traceback, io
        buf = io.StringIO()
        buf.write(f"\n{'='*60}\n[STUCK DEBUGGER] SIGUSR1 received — dumping all threads\n{'='*60}\n")
        for tid, tframe in sys._current_frames().items():
            buf.write(f"\n--- Thread {tid} ---\n")
            traceback.print_stack(tframe, file=buf)
        print(buf.getvalue(), flush=True)

    signal.signal(signal.SIGUSR1, _dump_on_alarm)

    def _watchdog():
        import time
        last_round = [-1]
        stall_count = [0]
        while True:
            time.sleep(60)
            try:
                with open("run_state.json") as f:
                    import json
                    state = json.load(f)
                cur = state.get("current_round", -1)
                if cur == last_round[0]:
                    stall_count[0] += 1
                    print(f"[WATCHDOG] round stuck at {cur} for {stall_count[0]} min", flush=True)
                    if stall_count[0] >= 2:
                        os.kill(os.getpid(), signal.SIGUSR1)
                else:
                    stall_count[0] = 0
                    last_round[0] = cur
            except Exception:
                pass

    t = threading.Thread(target=_watchdog, daemon=True)
    t.start()


_patch_openai_thinking_mode()
_install_stuck_debugger()


class UnicodeFormatter(logging.Formatter):
    """사용자 정의 포맷터, Unicode 이스케이프 시퀀스를 읽을 수 있는 문자로 변환"""

    UNICODE_ESCAPE_PATTERN = re.compile(r"\\u([0-9a-fA-F]{4})")

    def format(self, record):
        result = super().format(record)

        def replace_unicode(match):
            try:
                return chr(int(match.group(1), 16))
            except (ValueError, OverflowError):
                return match.group(0)

        return self.UNICODE_ESCAPE_PATTERN.sub(replace_unicode, result)


class MaxTokensWarningFilter(logging.Filter):
    """camel-ai의 max_tokens 관련 경고 필터링 (모델이 스스로 결정하도록 의도적으로 max_tokens를 설정하지 않음)"""

    def filter(self, record):
        # max_tokens 경고를 포함하는 로그 필터링
        if (
            "max_tokens" in record.getMessage()
            and "Invalid or missing" in record.getMessage()
        ):
            return False
        return True


# 모듈 로드 시 즉시 필터를 추가하여 camel 코드가 실행되기 전에 적용되도록 함
logging.getLogger().addFilter(MaxTokensWarningFilter())


def setup_oasis_logging(log_dir: str):
    """OASIS 로그 설정, 고정된 이름의 로그 파일 사용"""
    os.makedirs(log_dir, exist_ok=True)

    # 이전 로그 파일 정리
    for f in os.listdir(log_dir):
        old_log = os.path.join(log_dir, f)
        if os.path.isfile(old_log) and f.endswith(".log"):
            try:
                os.remove(old_log)
            except OSError:
                pass

    formatter = UnicodeFormatter("%(levelname)s - %(asctime)s - %(name)s - %(message)s")

    loggers_config = {
        "social.agent": os.path.join(log_dir, "social.agent.log"),
        "social.twitter": os.path.join(log_dir, "social.twitter.log"),
        "social.rec": os.path.join(log_dir, "social.rec.log"),
        "oasis.env": os.path.join(log_dir, "oasis.env.log"),
        "table": os.path.join(log_dir, "table.log"),
    }

    for logger_name, log_file in loggers_config.items():
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
        logger.handlers.clear()
        file_handler = logging.FileHandler(log_file, encoding="utf-8", mode="w")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        logger.propagate = False


try:
    from camel.models import ModelFactory
    from camel.types import ModelPlatformType
    import oasis
    from oasis import ActionType, LLMAction, ManualAction, generate_reddit_agent_graph
except ImportError as e:
    print(f"오류: 종속성 누락 {e}")
    print("먼저 설치하십시오: pip install oasis-ai camel-ai")
    sys.exit(1)


# IPC 관련 상수
IPC_COMMANDS_DIR = "ipc_commands"
IPC_RESPONSES_DIR = "ipc_responses"
ENV_STATUS_FILE = "env_status.json"


class CommandType:
    """명령 유형 상수"""

    INTERVIEW = "interview"
    BATCH_INTERVIEW = "batch_interview"
    CLOSE_ENV = "close_env"


class IPCHandler:
    """IPC 명령 처리기"""

    def __init__(self, simulation_dir: str, env, agent_graph):
        self.simulation_dir = simulation_dir
        self.env = env
        self.agent_graph = agent_graph
        self.commands_dir = os.path.join(simulation_dir, IPC_COMMANDS_DIR)
        self.responses_dir = os.path.join(simulation_dir, IPC_RESPONSES_DIR)
        self.status_file = os.path.join(simulation_dir, ENV_STATUS_FILE)
        self._running = True

        # 디렉토리 존재 확인
        os.makedirs(self.commands_dir, exist_ok=True)
        os.makedirs(self.responses_dir, exist_ok=True)

    def update_status(self, status: str):
        """환경 상태 업데이트"""
        with open(self.status_file, "w", encoding="utf-8") as f:
            json.dump(
                {"status": status, "timestamp": datetime.now().isoformat()},
                f,
                ensure_ascii=False,
                indent=2,
            )

    def poll_command(self) -> Optional[Dict[str, Any]]:
        """대기 중인 명령 폴링"""
        if not os.path.exists(self.commands_dir):
            return None

        # 명령 파일 가져오기 (시간순 정렬)
        command_files = []
        for filename in os.listdir(self.commands_dir):
            if filename.endswith(".json"):
                filepath = os.path.join(self.commands_dir, filename)
                command_files.append((filepath, os.path.getmtime(filepath)))

        command_files.sort(key=lambda x: x[1])

        for filepath, _ in command_files:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                continue

        return None

    def send_response(
        self, command_id: str, status: str, result: Dict = None, error: str = None
    ):
        """응답 전송"""
        response = {
            "command_id": command_id,
            "status": status,
            "result": result,
            "error": error,
            "timestamp": datetime.now().isoformat(),
        }

        response_file = os.path.join(self.responses_dir, f"{command_id}.json")
        with open(response_file, "w", encoding="utf-8") as f:
            json.dump(response, f, ensure_ascii=False, indent=2)

        # 명령 파일 삭제
        command_file = os.path.join(self.commands_dir, f"{command_id}.json")
        try:
            os.remove(command_file)
        except OSError:
            pass

    async def handle_interview(
        self, command_id: str, agent_id: int, prompt: str
    ) -> bool:
        """
        개별 에이전트 인터뷰 명령 처리

        Returns:
            True는 성공, False는 실패를 의미
        """
        try:
            # 에이전트 가져오기
            agent = self.agent_graph.get_agent(agent_id)

            # 인터뷰 액션 생성
            interview_action = ManualAction(
                action_type=ActionType.INTERVIEW, action_args={"prompt": prompt}
            )

            # 인터뷰 실행
            actions = {agent: interview_action}
            await self.env.step(actions)

            # 데이터베이스에서 결과 가져오기
            result = self._get_interview_result(agent_id)

            self.send_response(command_id, "completed", result=result)
            print(f"  인터뷰 완료: agent_id={agent_id}")
            return True

        except Exception as e:
            error_msg = str(e)
            print(f"  인터뷰 실패: agent_id={agent_id}, error={error_msg}")
            self.send_response(command_id, "failed", error=error_msg)
            return False

    async def handle_batch_interview(
        self, command_id: str, interviews: List[Dict]
    ) -> bool:
        """
        일괄 인터뷰 명령 처리

        Args:
            interviews: [{"agent_id": int, "prompt": str}, ...]
        """
        try:
            # 액션 딕셔너리 구성
            actions = {}
            agent_prompts = {}  # 각 에이전트의 프롬프트 기록

            for interview in interviews:
                agent_id = interview.get("agent_id")
                prompt = interview.get("prompt", "")

                try:
                    agent = self.agent_graph.get_agent(agent_id)
                    actions[agent] = ManualAction(
                        action_type=ActionType.INTERVIEW, action_args={"prompt": prompt}
                    )
                    agent_prompts[agent_id] = prompt
                except Exception as e:
                    print(f"  경고: 에이전트 {agent_id}를 가져올 수 없음: {e}")

            if not actions:
                self.send_response(command_id, "failed", error="유효한 에이전트 없음")
                return False

            # 일괄 인터뷰 실행
            await self.env.step(actions)

            # 모든 결과 가져오기
            results = {}
            for agent_id in agent_prompts.keys():
                result = self._get_interview_result(agent_id)
                results[agent_id] = result

            self.send_response(
                command_id,
                "completed",
                result={"interviews_count": len(results), "results": results},
            )
            print(f"  일괄 인터뷰 완료: {len(results)} 개 에이전트")
            return True

        except Exception as e:
            error_msg = str(e)
            print(f"  일괄 인터뷰 실패: {error_msg}")
            self.send_response(command_id, "failed", error=error_msg)
            return False

    def _get_interview_result(self, agent_id: int) -> Dict[str, Any]:
        """데이터베이스에서 최신 인터뷰 결과 가져오기"""
        db_path = os.path.join(self.simulation_dir, "reddit_simulation.db")

        result = {"agent_id": agent_id, "response": None, "timestamp": None}

        if not os.path.exists(db_path):
            return result

        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # 최신 인터뷰 기록 조회
            cursor.execute(
                """
                SELECT user_id, info, created_at
                FROM trace
                WHERE action = ? AND user_id = ?
                ORDER BY created_at DESC
                LIMIT 1
            """,
                (ActionType.INTERVIEW.value, agent_id),
            )

            row = cursor.fetchone()
            if row:
                user_id, info_json, created_at = row
                try:
                    info = json.loads(info_json) if info_json else {}
                    result["response"] = info.get("response", info)
                    result["timestamp"] = created_at
                except json.JSONDecodeError:
                    result["response"] = info_json

            conn.close()

        except Exception as e:
            print(f"  인터뷰 결과 읽기 실패: {e}")

        return result

    async def process_commands(self) -> bool:
        """
        모든 대기 중인 명령 처리

        Returns:
            True는 계속 실행, False는 종료를 의미
        """
        command = self.poll_command()
        if not command:
            return True

        command_id = command.get("command_id")
        command_type = command.get("command_type")
        args = command.get("args", {})

        print(f"\nIPC 명령 수신: {command_type}, id={command_id}")

        if command_type == CommandType.INTERVIEW:
            await self.handle_interview(
                command_id, args.get("agent_id", 0), args.get("prompt", "")
            )
            return True

        elif command_type == CommandType.BATCH_INTERVIEW:
            await self.handle_batch_interview(command_id, args.get("interviews", []))
            return True

        elif command_type == CommandType.CLOSE_ENV:
            print("환경 종료 명령 수신")
            self.send_response(
                command_id, "completed", result={"message": "환경이 곧 종료됩니다."}
            )
            return False

        else:
            self.send_response(
                command_id, "failed", error=f"알 수 없는 명령 유형: {command_type}"
            )
            return True


# ── 액션 로깅 지원 (run_state.json 업데이트 체인용) ──

FILTERED_ACTIONS = {"refresh", "sign_up"}

ACTION_TYPE_MAP = {
    "create_post": "CREATE_POST",
    "like_post": "LIKE_POST",
    "dislike_post": "DISLIKE_POST",
    "repost": "REPOST",
    "quote_post": "QUOTE_POST",
    "follow": "FOLLOW",
    "mute": "MUTE",
    "create_comment": "CREATE_COMMENT",
    "like_comment": "LIKE_COMMENT",
    "dislike_comment": "DISLIKE_COMMENT",
    "search_posts": "SEARCH_POSTS",
    "search_user": "SEARCH_USER",
    "trend": "TREND",
    "do_nothing": "DO_NOTHING",
    "interview": "INTERVIEW",
}


def _get_agent_names(config: Dict[str, Any]) -> Dict[int, str]:
    """simulation_config에서 agent_id -> entity_name 매핑"""
    names: Dict[int, str] = {}
    for ac in config.get("agent_configs", []):
        aid = ac.get("agent_id")
        if aid is not None:
            names[aid] = ac.get("entity_name", f"Agent_{aid}")
    return names


def _fetch_new_actions(
    db_path: str, last_rowid: int, agent_names: Dict[int, str]
) -> tuple:
    """데이터베이스에서 새로운 액션 가져오기 (last_rowid 이후)"""
    actions: List[Dict[str, Any]] = []
    new_last = last_rowid
    if not os.path.exists(db_path):
        return actions, new_last
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT rowid, user_id, action, info FROM trace WHERE rowid > ? ORDER BY rowid ASC",
            (last_rowid,),
        )
        for rowid, user_id, action, info_json in cur.fetchall():
            new_last = rowid
            if action in FILTERED_ACTIONS:
                continue
            try:
                args = json.loads(info_json) if info_json else {}
            except json.JSONDecodeError:
                args = {}
            simplified = {}
            for k in (
                "content", "post_id", "comment_id", "quoted_id",
                "new_post_id", "follow_id", "query", "like_id", "dislike_id",
            ):
                if k in args:
                    simplified[k] = args[k]
            actions.append({
                "agent_id": user_id,
                "agent_name": agent_names.get(user_id, f"Agent_{user_id}"),
                "action_type": ACTION_TYPE_MAP.get(action, action.upper()),
                "action_args": simplified,
            })
        conn.close()
    except Exception:
        pass
    return actions, new_last


class RedditSimulationRunner:
    """Reddit 시뮬레이션 실행기"""

    # Reddit 사용 가능 액션 (INTERVIEW 제외, INTERVIEW는 ManualAction을 통해서만 수동으로 트리거 가능)
    AVAILABLE_ACTIONS = [
        ActionType.LIKE_POST,
        ActionType.DISLIKE_POST,
        ActionType.CREATE_POST,
        ActionType.CREATE_COMMENT,
        ActionType.LIKE_COMMENT,
        ActionType.DISLIKE_COMMENT,
        ActionType.SEARCH_POSTS,
        ActionType.SEARCH_USER,
        ActionType.TREND,
        ActionType.REFRESH,
        ActionType.DO_NOTHING,
        ActionType.FOLLOW,
        ActionType.MUTE,
    ]

    def __init__(self, config_path: str, wait_for_commands: bool = True):
        """
        시뮬레이션 실행기 초기화

        Args:
            config_path: 설정 파일 경로 (simulation_config.json)
            wait_for_commands: 시뮬레이션 완료 후 명령 대기 여부 (기본값 True)
        """
        self.config_path = config_path
        self.config = self._load_config()
        self.simulation_dir = os.path.dirname(config_path)
        self.wait_for_commands = wait_for_commands
        self.tools_enabled = False
        self.geopolitics_enabled = False
        self._geo_platform = None
        self.env = None
        self.agent_graph = None
        self.ipc_handler = None

    def _load_config(self) -> Dict[str, Any]:
        """설정 파일 로드"""
        with open(self.config_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _get_profile_path(self) -> str:
        """프로필 파일 경로 가져오기"""
        return os.path.join(self.simulation_dir, "reddit_profiles.json")

    def _get_db_path(self) -> str:
        """데이터베이스 경로 가져오기"""
        return os.path.join(self.simulation_dir, "reddit_simulation.db")

    def _create_model(self):
        """
        LLM 모델 생성

        프로젝트 루트 디렉토리의 .env 파일 설정을 통합 사용 (우선순위 가장 높음):
        - LLM_API_KEY: API 키
        - LLM_BASE_URL: API 기본 URL
        - LLM_MODEL_NAME: 모델 이름
        """
        # .env에서 설정을 우선적으로 읽음
        llm_api_key = os.environ.get("LLM_API_KEY", "")
        llm_base_url = os.environ.get("LLM_BASE_URL", "")
        llm_model = os.environ.get("LLM_MODEL_NAME", "")

        # .env에 없는 경우 config를 백업으로 사용
        if not llm_model:
            llm_model = self.config.get("llm_model", "gpt-4o-mini")

        # camel-ai에 필요한 환경 변수 설정
        if llm_api_key:
            os.environ["OPENAI_API_KEY"] = llm_api_key

        if not os.environ.get("OPENAI_API_KEY"):
            raise ValueError(
                "API Key 설정이 누락되었습니다. 프로젝트 루트 디렉토리의 .env 파일에 LLM_API_KEY를 설정하십시오."
            )

        if llm_base_url:
            os.environ["OPENAI_API_BASE_URL"] = llm_base_url

        print(
            f"LLM 설정: model={llm_model}, base_url={llm_base_url[:40] if llm_base_url else '기본'}..."
        )

        return ModelFactory.create(
            model_platform=ModelPlatformType.OPENAI,
            model_type=llm_model,
        )

    def _get_active_agents_for_round(
        self, env, current_hour: int, round_num: int
    ) -> List:
        """
        시간 및 설정에 따라 이번 라운드에 활성화할 에이전트 결정
        """
        time_config = self.config.get("time_config", {})
        agent_configs = self.config.get("agent_configs", [])

        base_min = time_config.get("agents_per_hour_min", 5)
        base_max = time_config.get("agents_per_hour_max", 20)

        peak_hours = time_config.get("peak_hours", [9, 10, 11, 14, 15, 20, 21, 22])
        off_peak_hours = time_config.get("off_peak_hours", [0, 1, 2, 3, 4, 5])

        if current_hour in peak_hours:
            multiplier = time_config.get("peak_activity_multiplier", 1.5)
        elif current_hour in off_peak_hours:
            multiplier = time_config.get("off_peak_activity_multiplier", 0.3)
        else:
            multiplier = 1.0

        target_count = int(random.uniform(base_min, base_max) * multiplier)

        candidates = []
        for cfg in agent_configs:
            agent_id = cfg.get("agent_id", 0)
            active_hours = cfg.get("active_hours", list(range(8, 23)))
            activity_level = cfg.get("activity_level", 0.5)

            if current_hour not in active_hours:
                continue

            if random.random() < activity_level:
                candidates.append(agent_id)

        selected_ids = (
            random.sample(candidates, min(target_count, len(candidates)))
            if candidates
            else []
        )

        active_agents = []
        for agent_id in selected_ids:
            try:
                agent = env.agent_graph.get_agent(agent_id)
                active_agents.append((agent_id, agent))
            except Exception:
                pass

        return active_agents

    async def run(self, max_rounds: int = None):
        """Reddit 시뮬레이션 실행

        Args:
            max_rounds: 최대 시뮬레이션 라운드 수 (선택 사항, 너무 긴 시뮬레이션을 자르기 위해 사용)
        """
        print("=" * 60)
        print("OASIS Reddit 시뮬레이션")
        print(f"설정 파일: {self.config_path}")
        print(f"시뮬레이션 ID: {self.config.get('simulation_id', 'unknown')}")
        print(f"명령 대기 모드: {'활성화' if self.wait_for_commands else '비활성화'}")
        print("=" * 60)

        time_config = self.config.get("time_config", {})
        total_hours = time_config.get("total_simulation_hours", 72)
        minutes_per_round = time_config.get("minutes_per_round", 30)
        total_rounds = (total_hours * 60) // minutes_per_round

        # 최대 라운드 수가 지정된 경우 자름
        if max_rounds is not None and max_rounds > 0:
            original_rounds = total_rounds
            total_rounds = min(total_rounds, max_rounds)
            if total_rounds < original_rounds:
                print(
                    f"\n라운드 수가 잘렸습니다: {original_rounds} -> {total_rounds} (max_rounds={max_rounds})"
                )

        print(f"\n시뮬레이션 파라미터:")
        print(f"  - 총 시뮬레이션 시간: {total_hours}시간")
        print(f"  - 라운드당 시간: {minutes_per_round}분")
        print(f"  - 총 라운드 수: {total_rounds}")
        if max_rounds:
            print(f"  - 최대 라운드 수 제한: {max_rounds}")
        print(f"  - 에이전트 수: {len(self.config.get('agent_configs', []))}")

        print("\nLLM 모델 초기화 중...")
        model = self._create_model()
        model.model_config_dict.setdefault(
            "extra_body", {}
        ).setdefault("chat_template_kwargs", {"enable_thinking": False})

        print("에이전트 프로필 로드 중...")
        profile_path = self._get_profile_path()
        if not os.path.exists(profile_path):
            print(f"오류: 프로필 파일이 존재하지 않음: {profile_path}")
            return

        self.agent_graph = await generate_reddit_agent_graph(
            profile_path=profile_path,
            model=model,
            available_actions=self.AVAILABLE_ACTIONS,
        )

        if self.tools_enabled:
            try:
                from camel.toolkits import SearchToolkit
                search_tools = [SearchToolkit().search_duckduckgo]
                for agent in self.agent_graph.get_agents():
                    if hasattr(agent, 'tools'):
                        agent.tools = search_tools
                    if hasattr(agent, 'single_iteration'):
                        agent.single_iteration = False
                print(f"SearchToolkit 주입 완료: {len(self.agent_graph.get_agents())}개 에이전트")
            except ImportError:
                print("경고: camel-ai[tools] 패키지가 설치되지 않아 검색 도구를 사용할 수 없습니다")
            except Exception as e:
                print(f"경고: 검색 도구 주입 실패: {e}")

        db_path = self._get_db_path()
        if os.path.exists(db_path):
            os.remove(db_path)
            print(f"이전 데이터베이스 삭제됨: {db_path}")

        print("OASIS 환경 생성 중...")
        self.env = oasis.make(
            agent_graph=self.agent_graph,
            platform=oasis.DefaultPlatformType.REDDIT,
            database_path=db_path,
            semaphore=30,  # 최대 동시 LLM 요청 수를 제한하여 API 과부하 방지
        )

        if self.geopolitics_enabled:
            try:
                from app.platforms.geopolitics_platform import GeopoliticsPlatform
                geo_events_path = os.path.join(self.simulation_dir, "geopolitics_events.jsonl")

                def _persist_event(event: dict):
                    with open(geo_events_path, "a", encoding="utf-8") as f:
                        f.write(json.dumps(event, ensure_ascii=False) + "\n")

                self._geo_platform = GeopoliticsPlatform(event_callback=_persist_event)
                print(f"GeopoliticsPlatform 주입 완료 (이벤트 저장: {geo_events_path})")
            except ImportError:
                print("경고: GeopoliticsPlatform을 로드할 수 없습니다")
            except Exception as e:
                print(f"경고: GeopoliticsPlatform 주입 실패: {e}")

        await self.env.reset()
        print("환경 초기화 완료\n")

        action_logger = PlatformActionLogger("reddit", self.simulation_dir)
        agent_names = _get_agent_names(self.config)
        for agent_id, agent in self.agent_graph.get_agents():
            if agent_id not in agent_names:
                agent_names[agent_id] = getattr(agent, "name", f"Agent_{agent_id}")
        last_rowid = 0
        total_actions = 0
        action_logger.log_simulation_start(self.config)

        # IPC 처리기 초기화
        self.ipc_handler = IPCHandler(self.simulation_dir, self.env, self.agent_graph)
        self.ipc_handler.update_status("running")

        # 초기 이벤트 실행
        event_config = self.config.get("event_config", {})
        initial_posts = event_config.get("initial_posts", [])

        action_logger.log_round_start(0, 0)
        initial_action_count = 0

        if initial_posts:
            print(f"초기 이벤트 실행 ({len(initial_posts)}개의 초기 게시물)...")
            initial_actions = {}
            for post in initial_posts:
                agent_id = post.get("poster_agent_id", 0)
                content = post.get("content", "")
                try:
                    agent = self.env.agent_graph.get_agent(agent_id)
                    if agent in initial_actions:
                        if not isinstance(initial_actions[agent], list):
                            initial_actions[agent] = [initial_actions[agent]]
                        initial_actions[agent].append(
                            ManualAction(
                                action_type=ActionType.CREATE_POST,
                                action_args={"content": content},
                            )
                        )
                    else:
                        initial_actions[agent] = ManualAction(
                            action_type=ActionType.CREATE_POST,
                            action_args={"content": content},
                        )
                except Exception as e:
                    print(
                        f"  경고: 에이전트 {agent_id}에 대한 초기 게시물을 생성할 수 없음: {e}"
                    )

            if initial_actions:
                await self.env.step(initial_actions)
                print(f"  {len(initial_actions)}개의 초기 게시물이 게시되었습니다.")

                new_actions, last_rowid = _fetch_new_actions(db_path, last_rowid, agent_names)
                for a in new_actions:
                    action_logger.log_action(
                        round_num=0,
                        agent_id=a["agent_id"],
                        agent_name=a["agent_name"],
                        action_type=a["action_type"],
                        action_args=a["action_args"],
                    )
                    total_actions += 1
                    initial_action_count += 1

        action_logger.log_round_end(0, initial_action_count)

        # 메인 시뮬레이션 루프
        print("\n시뮬레이션 루프 시작...")
        start_time = datetime.now()

        start_hour = time_config.get("start_hour", 9)
        start_offset_minutes = start_hour * 60

        for round_num in range(total_rounds):
            simulated_minutes = start_offset_minutes + round_num * minutes_per_round
            simulated_hour = (simulated_minutes // 60) % 24
            simulated_day = simulated_minutes // (60 * 24) + 1

            active_agents = self._get_active_agents_for_round(
                self.env, simulated_hour, round_num
            )

            action_logger.log_round_start(round_num + 1, simulated_hour)

            if not active_agents:
                action_logger.log_round_end(round_num + 1, 0)
                continue

            actions = {agent: LLMAction() for _, agent in active_agents}

            await self.env.step(actions)

            new_actions, last_rowid = _fetch_new_actions(db_path, last_rowid, agent_names)
            round_action_count = 0
            for a in new_actions:
                action_logger.log_action(
                    round_num=round_num + 1,
                    agent_id=a["agent_id"],
                    agent_name=a["agent_name"],
                    action_type=a["action_type"],
                    action_args=a["action_args"],
                )
                total_actions += 1
                round_action_count += 1

            action_logger.log_round_end(round_num + 1, round_action_count)

            if (round_num + 1) % 10 == 0 or round_num == 0:
                elapsed = (datetime.now() - start_time).total_seconds()
                progress = (round_num + 1) / total_rounds * 100
                print(
                    f"  [Day {simulated_day}, {simulated_hour:02d}:00] "
                    f"Round {round_num + 1}/{total_rounds} ({progress:.1f}%) "
                    f"- {len(active_agents)} agents active "
                    f"- elapsed: {elapsed:.1f}s"
                )

        action_logger.log_simulation_end(total_rounds, total_actions)

        total_elapsed = (datetime.now() - start_time).total_seconds()
        print(f"\n시뮬레이션 루프 완료!")
        print(f"  - 총 소요 시간: {total_elapsed:.1f}초")
        print(f"  - 총 액션 수: {total_actions}")
        print(f"  - 데이터베이스: {db_path}")

        # 명령 대기 모드 진입 여부
        if self.wait_for_commands:
            print("\n" + "=" * 60)
            print("명령 대기 모드 진입 - 환경 유지 중")
            print("지원되는 명령: interview, batch_interview, close_env")
            print("=" * 60)

            self.ipc_handler.update_status("alive")

            # 명령 대기 루프 (전역 _shutdown_event 사용)
            try:
                while not _shutdown_event.is_set():
                    should_continue = await self.ipc_handler.process_commands()
                    if not should_continue:
                        break
                    try:
                        await asyncio.wait_for(_shutdown_event.wait(), timeout=0.5)
                        break  # 종료 시그널 수신
                    except asyncio.TimeoutError:
                        pass
            except KeyboardInterrupt:
                print("\n중단 시그널 수신")
            except asyncio.CancelledError:
                print("\n작업 취소됨")
            except Exception as e:
                print(f"\n명령 처리 오류: {e}")

            print("\n환경 종료 중...")

        # 환경 종료
        self.ipc_handler.update_status("stopped")
        await self.env.close()

        print("환경이 종료되었습니다.")
        print("=" * 60)


async def main():
    parser = argparse.ArgumentParser(description="OASIS Reddit 시뮬레이션")
    parser.add_argument(
        "--config",
        type=str,
        required=True,
        help="설정 파일 경로 (simulation_config.json)",
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=None,
        help="최대 시뮬레이션 라운드 수 (선택 사항, 너무 긴 시뮬레이션을 자르기 위해 사용)",
    )
    parser.add_argument(
        "--no-wait",
        action="store_true",
        default=False,
        help="시뮬레이션 완료 후 환경을 즉시 종료하고 명령 대기 모드로 진입하지 않음",
    )
    parser.add_argument(
        "--tools-enabled",
        action="store_true",
        default=False,
        help="에이전트에 DuckDuckGo 검색 도구 주입",
    )
    parser.add_argument(
        "--geopolitics-enabled",
        action="store_true",
        default=False,
        help="GeopoliticsPlatform을 OASIS 환경에 주입",
    )

    args = parser.parse_args()

    # main 함수 시작 시 shutdown 이벤트 생성
    global _shutdown_event
    _shutdown_event = asyncio.Event()

    if not os.path.exists(args.config):
        print(f"오류: 설정 파일이 존재하지 않음: {args.config}")
        sys.exit(1)

    # 시뮬레이션 로그 설정 초기화 (고정 파일 이름 사용, 이전 로그 정리)
    simulation_dir = os.path.dirname(args.config) or "."
    setup_oasis_logging(os.path.join(simulation_dir, "log"))

    runner = RedditSimulationRunner(
        config_path=args.config, wait_for_commands=not args.no_wait
    )
    runner.tools_enabled = args.tools_enabled
    runner.geopolitics_enabled = args.geopolitics_enabled
    await runner.run(max_rounds=args.max_rounds)


def setup_signal_handlers():
    """
    SIGTERM/SIGINT 수신 시 올바르게 종료되도록 시그널 처리기 설정
    프로그램이 리소스를 정상적으로 정리할 기회 제공 (데이터베이스, 환경 종료 등)
    """

    def signal_handler(signum, frame):
        global _cleanup_done
        sig_name = "SIGTERM" if signum == signal.SIGTERM else "SIGINT"
        print(f"\n{sig_name} 시그널을 수신했습니다. 종료 중...")
        if not _cleanup_done:
            _cleanup_done = True
            if _shutdown_event:
                _shutdown_event.set()
        else:
            # 시그널을 반복해서 수신하는 경우에만 강제 종료
            print("강제 종료 중...")
            sys.exit(1)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)


if __name__ == "__main__":
    setup_signal_handlers()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n프로그램이 중단되었습니다.")
    except SystemExit:
        pass
    finally:
        print("시뮬레이션 프로세스가 종료되었습니다.")
