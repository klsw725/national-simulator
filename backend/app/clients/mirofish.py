"""MiroFish HTTP 클라이언트.

MiroFish 6단계 파이프라인 API를 호출한다.

⚠️  AGENTS.md 경고: SPEC의 엔드포인트는 실제와 다름.
    이 클라이언트는 실제 MiroFish API 라우트를 사용한다.

Pipeline:
  1. POST /api/graph/ontology/generate  (multipart, 동기)
  2. POST /api/graph/build              (비동기 → poll task)
  3. POST /api/simulation/create        (동기)
  4. POST /api/simulation/prepare       (비동기 → poll task)
  5. POST /api/simulation/start         (비동기 → poll run-status)
  6. POST /api/report/generate          (비동기 → poll task)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.constants import (
    CLIENT_LONG_TIMEOUT,
    CLIENT_RETRY_ATTEMPTS,
    CLIENT_RETRY_WAIT_MAX,
    CLIENT_RETRY_WAIT_MIN,
    MIROFISH_CLOSE_ENV_TIMEOUT,
    MIROFISH_HEALTHCHECK_TIMEOUT,
    MIROFISH_INTERVIEW_ALL_TIMEOUT,
    MIROFISH_INTERVIEW_BATCH_TIMEOUT,
    MIROFISH_INTERVIEW_TIMEOUT,
    MIROFISH_PIPELINE_TIMEOUT,
    MIROFISH_POLL_INTERVAL,
    MIROFISH_POLL_TIMEOUT,
    MIROFISH_TIMEOUT_BUFFER,
)
from app.services.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)


class MiroFishClient:
    def __init__(self, base_url: str, timeout: float = CLIENT_LONG_TIMEOUT):
        self.base_url = base_url
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout)
        self._circuit_breaker = CircuitBreaker(name="mirofish")

    @retry(
        stop=stop_after_attempt(CLIENT_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=CLIENT_RETRY_WAIT_MIN, max=CLIENT_RETRY_WAIT_MAX),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """재시도 + 서킷 브레이커를 적용한 HTTP 요청."""
        async def _do():
            return await getattr(self._client, method)(url, **kwargs)
        return await self._circuit_breaker.call(_do)

    # ------------------------------------------------------------------
    # Step 1: 온톨로지 생성 (동기)
    # ------------------------------------------------------------------

    async def generate_ontology(
        self,
        seed_text: str,
        seed_filename: str,
        simulation_requirement: str,
        project_name: str = "osint-simulation",
        additional_context: str = "",
    ) -> dict[str, Any]:
        """POST /api/graph/ontology/generate (multipart/form-data).

        Returns: {"project_id": ..., "ontology": {...}, ...}
        """
        files = {"files": (seed_filename, seed_text.encode("utf-8"), "text/markdown")}
        data: dict[str, str] = {
            "simulation_requirement": simulation_requirement,
            "project_name": project_name,
        }
        if additional_context:
            data["additional_context"] = additional_context

        resp = await self._request("post", "/api/graph/ontology/generate",
        files=files,
        data=data,
        timeout=MIROFISH_PIPELINE_TIMEOUT,)
        resp.raise_for_status()
        body = resp.json()
        return body.get("data", body)

    # ------------------------------------------------------------------
    # Step 2: 그래프 빌드 (비동기)
    # ------------------------------------------------------------------

    async def build_graph(self, project_id: str) -> str:
        """POST /api/graph/build → task_id"""
        resp = await self._request("post", "/api/graph/build",
        json={"project_id": project_id},)
        resp.raise_for_status()
        body = resp.json()
        return body.get("data", body).get("task_id", "")

    async def get_task_status(self, task_id: str) -> dict[str, Any]:
        """GET /api/graph/task/{task_id} → {status, progress, ...}"""
        resp = await self._request("get", f"/api/graph/task/{task_id}")
        resp.raise_for_status()
        body = resp.json()
        return body.get("data", body)

    # ------------------------------------------------------------------
    # Step 3: 시뮬레이션 생성 (동기)
    # ------------------------------------------------------------------

    async def create_simulation(
        self,
        project_id: str,
        graph_id: str | None = None,
        enable_twitter: bool = True,
        enable_reddit: bool = False,
    ) -> dict[str, Any]:
        """POST /api/simulation/create → {simulation_id, ...}"""
        payload: dict[str, Any] = {
            "project_id": project_id,
            "enable_twitter": enable_twitter,
            "enable_reddit": enable_reddit,
        }
        if graph_id:
            payload["graph_id"] = graph_id

        resp = await self._request("post", "/api/simulation/create", json=payload)
        resp.raise_for_status()
        body = resp.json()
        return body.get("data", body)

    # ------------------------------------------------------------------
    # Step 4: 시뮬레이션 준비 (비동기 — 프로필 생성 포함)
    # ------------------------------------------------------------------

    async def prepare_simulation(self, simulation_id: str) -> str:
        """POST /api/simulation/prepare → task_id"""
        resp = await self._request("post", "/api/simulation/prepare",
        json={
            "simulation_id": simulation_id,
            "use_llm_for_profiles": True,
        },
        timeout=MIROFISH_PIPELINE_TIMEOUT,)
        resp.raise_for_status()
        body = resp.json()
        data = body.get("data", body)
        # 이미 준비 완료인 경우
        if data.get("already_prepared"):
            return ""
        return data.get("task_id", "")

    async def get_prepare_status(self, task_id: str) -> dict[str, Any]:
        """POST /api/simulation/prepare/status → {status, progress}"""
        resp = await self._request("post", "/api/simulation/prepare/status",
        json={"task_id": task_id},)
        resp.raise_for_status()
        body = resp.json()
        return body.get("data", body)

    async def get_simulation_state(self, simulation_id: str) -> dict[str, Any]:
        """GET /api/simulation/{id} → {status, error, ...}"""
        resp = await self._request("get", f"/api/simulation/{simulation_id}")
        resp.raise_for_status()
        body = resp.json()
        return body.get("data", body)

    # ------------------------------------------------------------------
    # Step 5: 시뮬레이션 실행
    # ------------------------------------------------------------------

    async def start_simulation(
        self,
        simulation_id: str,
        platform: str = "twitter",
        max_rounds: int = 10,
        simulation_hours: int | None = None,
        tools_enabled: bool = False,
        geopolitics_enabled: bool = False,
    ) -> dict[str, Any]:
        """POST /api/simulation/start → {runner_status, ...}"""
        payload: dict[str, Any] = {
            "simulation_id": simulation_id,
            "platform": platform,
            "max_rounds": max_rounds,
        }
        if simulation_hours is not None:
            payload["total_simulation_hours"] = simulation_hours
        if tools_enabled:
            payload["tools_enabled"] = True
        if geopolitics_enabled:
            payload["geopolitics_enabled"] = True

        resp = await self._request("post", "/api/simulation/start", json=payload)
        resp.raise_for_status()
        body = resp.json()
        return body.get("data", body)

    async def get_run_status(self, simulation_id: str) -> dict[str, Any]:
        """GET /api/simulation/{id}/run-status"""
        resp = await self._request("get", f"/api/simulation/{simulation_id}/run-status")
        resp.raise_for_status()
        body = resp.json()
        return body.get("data", body)

    async def stop_simulation(self, simulation_id: str) -> dict[str, Any]:
        """POST /api/simulation/stop"""
        resp = await self._request("post", "/api/simulation/stop",
        json={"simulation_id": simulation_id},)
        resp.raise_for_status()
        body = resp.json()
        return body.get("data", body)

    async def start_round_control(
        self,
        simulation_id: str,
        platform: str = "twitter",
        max_rounds: int = 10,
        tools_enabled: bool = False,
        geopolitics_enabled: bool = False,
    ) -> dict[str, Any]:
        resp = await self._request(
            "post",
            "/api/simulation/round_control/start",
            json={
                "simulation_id": simulation_id,
                "platform": platform,
                "max_rounds": max_rounds,
                "tools_enabled": tools_enabled,
                "geopolitics_enabled": geopolitics_enabled,
            },
            timeout=120,
        )
        resp.raise_for_status()
        body = resp.json()
        return body.get("data", body)

    async def proceed_round(
        self,
        simulation_id: str,
        round_num: int,
        inject_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"simulation_id": simulation_id, "round": round_num}
        if inject_context is not None:
            payload["inject_context"] = inject_context
        resp = await self._request(
            "post",
            "/api/simulation/round_control/proceed",
            json=payload,
            timeout=300,
        )
        resp.raise_for_status()
        body = resp.json()
        return body.get("data", body)

    async def stop_round_control(
        self,
        simulation_id: str,
        reason: str = "completed",
    ) -> dict[str, Any]:
        resp = await self._request(
            "post",
            "/api/simulation/round_control/stop",
            json={"simulation_id": simulation_id, "reason": reason},
        )
        resp.raise_for_status()
        body = resp.json()
        return body.get("data", body)

    async def heartbeat_round_control(
        self,
        simulation_id: str,
        timestamp: str,
    ) -> dict[str, Any]:
        resp = await self._request(
            "post",
            "/api/simulation/round_control/heartbeat",
            json={"simulation_id": simulation_id, "timestamp": timestamp},
            timeout=30,
        )
        resp.raise_for_status()
        body = resp.json()
        return body.get("data", body)

    # ------------------------------------------------------------------
    # Step 6: 보고서 생성 (비동기)
    # ------------------------------------------------------------------

    async def generate_report(self, simulation_id: str) -> str:
        """POST /api/report/generate → task_id"""
        resp = await self._request("post", "/api/report/generate",
        json={"simulation_id": simulation_id},
        timeout=MIROFISH_PIPELINE_TIMEOUT,)
        resp.raise_for_status()
        body = resp.json()
        data = body.get("data", body)
        if data.get("already_generated"):
            return ""
        return data.get("task_id", "")

    async def get_report_status(self, task_id: str) -> dict[str, Any]:
        """POST /api/report/generate/status"""
        resp = await self._request("post", "/api/report/generate/status",
        json={"task_id": task_id},)
        resp.raise_for_status()
        body = resp.json()
        return body.get("data", body)

    async def get_report_by_simulation(self, simulation_id: str) -> dict[str, Any]:
        """GET /api/report/by-simulation/{simulation_id}"""
        resp = await self._request("get", f"/api/report/by-simulation/{simulation_id}")
        resp.raise_for_status()
        body = resp.json()
        return body.get("data", body)

    # ------------------------------------------------------------------
    # 결과 조회
    # ------------------------------------------------------------------

    async def get_simulation_actions(
        self, simulation_id: str, platform: str = "twitter",
        limit: int = 200, offset: int = 0,
    ) -> dict[str, Any]:
        """GET /api/simulation/{id}/actions"""
        resp = await self._request("get", f"/api/simulation/{simulation_id}/actions",
        params={"platform": platform, "limit": limit, "offset": offset},)
        resp.raise_for_status()
        body = resp.json()
        return body.get("data", body)

    async def get_simulation_posts(
        self, simulation_id: str, platform: str = "twitter", limit: int = 100
    ) -> dict[str, Any]:
        """GET /api/simulation/{id}/posts"""
        resp = await self._request("get", f"/api/simulation/{simulation_id}/posts",
        params={"platform": platform, "limit": limit},)
        resp.raise_for_status()
        body = resp.json()
        return body.get("data", body)

    # ------------------------------------------------------------------
    # Realtime monitoring
    # ------------------------------------------------------------------

    async def get_graph_data(self, graph_id: str) -> dict[str, Any]:
        """GET /api/graph/data/{graph_id} — 그래프 노드+엣지 데이터."""
        resp = await self._request("get", f"/api/graph/data/{graph_id}")
        resp.raise_for_status()
        body = resp.json()
        return body.get("data", body)

    async def get_agent_stats(self, simulation_id: str) -> dict[str, Any]:
        """GET /api/simulation/{id}/agent-stats — 에이전트 활동 통계."""
        resp = await self._request("get", f"/api/simulation/{simulation_id}/agent-stats")
        resp.raise_for_status()
        body = resp.json()
        return body.get("data", body)

    async def get_profiles_realtime(self, simulation_id: str, platform: str = "twitter") -> dict[str, Any]:
        """GET /api/simulation/{id}/profiles/realtime — 프로필 생성 실시간 진행."""
        resp = await self._request("get", f"/api/simulation/{simulation_id}/profiles/realtime",
        params={"platform": platform},)
        resp.raise_for_status()
        body = resp.json()
        return body.get("data", body)

    async def get_config_realtime(self, simulation_id: str) -> dict[str, Any]:
        """GET /api/simulation/{id}/config/realtime — 설정 생성 실시간 진행."""
        resp = await self._request("get", f"/api/simulation/{simulation_id}/config/realtime")
        resp.raise_for_status()
        body = resp.json()
        return body.get("data", body)

    async def get_simulation_config(self, simulation_id: str) -> dict[str, Any]:
        """GET /api/simulation/{id}/config — 시뮬레이션 설정 조회."""
        resp = await self._request("get", f"/api/simulation/{simulation_id}/config")
        resp.raise_for_status()
        body = resp.json()
        return body.get("data", body)

    async def patch_simulation_config(self, simulation_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        """PATCH /api/simulation/{id}/config — 시뮬레이션 설정 부분 업데이트."""
        resp = await self._request("patch", f"/api/simulation/{simulation_id}/config", json=patch)
        resp.raise_for_status()
        body = resp.json()
        return body.get("data", body)

    # ------------------------------------------------------------------
    # Interview (명령 대기 모드)
    # ------------------------------------------------------------------

    async def get_env_status(self, simulation_id: str) -> dict[str, Any]:
        """POST /api/simulation/env-status — 환경 활성 여부 확인."""
        resp = await self._request(
            "post",
            "/api/simulation/env-status",
            json={"simulation_id": simulation_id},
        )
        resp.raise_for_status()
        body = resp.json()
        return body.get("data", body)

    async def interview_agent(
        self,
        simulation_id: str,
        agent_id: int,
        prompt: str,
        platform: str | None = None,
        timeout: int = MIROFISH_INTERVIEW_TIMEOUT,
    ) -> dict[str, Any]:
        """POST /api/simulation/interview — 단일 에이전트 인터뷰."""
        payload: dict[str, Any] = {
            "simulation_id": simulation_id,
            "agent_id": agent_id,
            "prompt": prompt,
            "timeout": timeout,
        }
        if platform:
            payload["platform"] = platform
        resp = await self._request(
            "post", "/api/simulation/interview", json=payload, timeout=float(timeout + MIROFISH_TIMEOUT_BUFFER),
        )
        resp.raise_for_status()
        body = resp.json()
        return body.get("data", body)

    async def interview_all_agents(
        self,
        simulation_id: str,
        prompt: str,
        platform: str | None = None,
        timeout: int = MIROFISH_INTERVIEW_ALL_TIMEOUT,
    ) -> dict[str, Any]:
        """POST /api/simulation/interview/all — 전체 에이전트 인터뷰."""
        payload: dict[str, Any] = {
            "simulation_id": simulation_id,
            "prompt": prompt,
            "timeout": timeout,
        }
        if platform:
            payload["platform"] = platform
        resp = await self._request(
            "post", "/api/simulation/interview/all", json=payload, timeout=float(timeout + MIROFISH_TIMEOUT_BUFFER),
        )
        resp.raise_for_status()
        body = resp.json()
        return body.get("data", body)

    async def interview_agents_batch(
        self,
        simulation_id: str,
        interviews: list[dict[str, Any]],
        platform: str | None = None,
        timeout: int = MIROFISH_INTERVIEW_BATCH_TIMEOUT,
    ) -> dict[str, Any]:
        """POST /api/simulation/interview/batch — 일괄 인터뷰."""
        payload: dict[str, Any] = {
            "simulation_id": simulation_id,
            "interviews": interviews,
            "timeout": timeout,
        }
        if platform:
            payload["platform"] = platform
        resp = await self._request(
            "post", "/api/simulation/interview/batch", json=payload, timeout=float(timeout + MIROFISH_TIMEOUT_BUFFER),
        )
        resp.raise_for_status()
        body = resp.json()
        return body.get("data", body)

    async def get_interview_history(
        self,
        simulation_id: str,
        agent_id: int | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """POST /api/simulation/interview/history — 인터뷰 기록 조회."""
        payload: dict[str, Any] = {
            "simulation_id": simulation_id,
            "limit": limit,
        }
        if agent_id is not None:
            payload["agent_id"] = agent_id
        resp = await self._request(
            "post", "/api/simulation/interview/history", json=payload,
        )
        resp.raise_for_status()
        body = resp.json()
        return body.get("data", body)

    async def close_env(self, simulation_id: str, timeout: int = MIROFISH_CLOSE_ENV_TIMEOUT) -> dict[str, Any]:
        """POST /api/simulation/close-env — 환경 종료."""
        resp = await self._request(
            "post",
            "/api/simulation/close-env",
            json={"simulation_id": simulation_id, "timeout": timeout},
            timeout=float(timeout + MIROFISH_TIMEOUT_BUFFER),
        )
        resp.raise_for_status()
        body = resp.json()
        return body.get("data", body)

    # ------------------------------------------------------------------
    # 폴링 유틸리티
    # ------------------------------------------------------------------

    async def poll_until_done(
        self,
        poll_fn,
        interval: float = MIROFISH_POLL_INTERVAL,
        timeout: float | None = MIROFISH_POLL_TIMEOUT,
        status_key: str = "status",
        done_values: tuple[str, ...] = ("completed",),
        fail_values: tuple[str, ...] = ("failed",),
    ) -> dict[str, Any]:
        """비동기 태스크 완료까지 폴링.

        Args:
            poll_fn: 호출할 비동기 함수 (인자 없음, dict 반환)
            interval: 폴링 간격 (초)
            timeout: 최대 대기 시간 (초)
            status_key: 상태 필드 이름
            done_values: 완료 상태 값
            fail_values: 실패 상태 값
        """
        elapsed = 0.0
        while timeout is None or timeout <= 0 or elapsed < timeout:
            result = await poll_fn()
            status = result.get(status_key, "")
            progress = result.get("progress", 0)

            if status in done_values:
                logger.info("Task completed (status=%s)", status)
                return result

            if status in fail_values:
                msg = result.get("error", result.get("message", "Unknown error"))
                raise RuntimeError(f"Task failed: {msg}")

            logger.debug(
                "Polling... status=%s progress=%s elapsed=%.0fs",
                status, progress, elapsed,
            )
            await asyncio.sleep(interval)
            elapsed += interval

        raise TimeoutError(f"Task timed out after {timeout}s")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def health_check(self) -> bool:
        """MiroFish 서버 상태 확인."""
        try:
            resp = await self._client.get("/api/graph/project/list", timeout=MIROFISH_HEALTHCHECK_TIMEOUT)
            return resp.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException):
            return False

    async def close(self) -> None:
        await self._client.aclose()
