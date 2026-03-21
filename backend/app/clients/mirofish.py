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

logger = logging.getLogger(__name__)


class MiroFishClient:
    def __init__(self, base_url: str, timeout: float = 120.0):
        self.base_url = base_url
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout)

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

        resp = await self._client.post(
            "/api/graph/ontology/generate",
            files=files,
            data=data,
            timeout=180.0,
        )
        resp.raise_for_status()
        body = resp.json()
        return body.get("data", body)

    # ------------------------------------------------------------------
    # Step 2: 그래프 빌드 (비동기)
    # ------------------------------------------------------------------

    async def build_graph(self, project_id: str) -> str:
        """POST /api/graph/build → task_id"""
        resp = await self._client.post(
            "/api/graph/build",
            json={"project_id": project_id},
        )
        resp.raise_for_status()
        body = resp.json()
        return body.get("data", body).get("task_id", "")

    async def get_task_status(self, task_id: str) -> dict[str, Any]:
        """GET /api/graph/task/{task_id} → {status, progress, ...}"""
        resp = await self._client.get(f"/api/graph/task/{task_id}")
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

        resp = await self._client.post("/api/simulation/create", json=payload)
        resp.raise_for_status()
        body = resp.json()
        return body.get("data", body)

    # ------------------------------------------------------------------
    # Step 4: 시뮬레이션 준비 (비동기 — 프로필 생성 포함)
    # ------------------------------------------------------------------

    async def prepare_simulation(self, simulation_id: str) -> str:
        """POST /api/simulation/prepare → task_id"""
        resp = await self._client.post(
            "/api/simulation/prepare",
            json={
                "simulation_id": simulation_id,
                "use_llm_for_profiles": True,
            },
            timeout=180.0,
        )
        resp.raise_for_status()
        body = resp.json()
        data = body.get("data", body)
        # 이미 준비 완료인 경우
        if data.get("already_prepared"):
            return ""
        return data.get("task_id", "")

    async def get_prepare_status(self, task_id: str) -> dict[str, Any]:
        """POST /api/simulation/prepare/status → {status, progress}"""
        resp = await self._client.post(
            "/api/simulation/prepare/status",
            json={"task_id": task_id},
        )
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
    ) -> dict[str, Any]:
        """POST /api/simulation/start → {runner_status, ...}"""
        payload: dict[str, Any] = {
            "simulation_id": simulation_id,
            "platform": platform,
            "max_rounds": max_rounds,
        }
        if simulation_hours is not None:
            payload["total_simulation_hours"] = simulation_hours

        resp = await self._client.post("/api/simulation/start", json=payload)
        resp.raise_for_status()
        body = resp.json()
        return body.get("data", body)

    async def get_run_status(self, simulation_id: str) -> dict[str, Any]:
        """GET /api/simulation/{id}/run-status"""
        resp = await self._client.get(
            f"/api/simulation/{simulation_id}/run-status"
        )
        resp.raise_for_status()
        body = resp.json()
        return body.get("data", body)

    async def stop_simulation(self, simulation_id: str) -> dict[str, Any]:
        """POST /api/simulation/stop"""
        resp = await self._client.post(
            "/api/simulation/stop",
            json={"simulation_id": simulation_id},
        )
        resp.raise_for_status()
        body = resp.json()
        return body.get("data", body)

    # ------------------------------------------------------------------
    # Step 6: 보고서 생성 (비동기)
    # ------------------------------------------------------------------

    async def generate_report(self, simulation_id: str) -> str:
        """POST /api/report/generate → task_id"""
        resp = await self._client.post(
            "/api/report/generate",
            json={"simulation_id": simulation_id},
            timeout=180.0,
        )
        resp.raise_for_status()
        body = resp.json()
        data = body.get("data", body)
        if data.get("already_generated"):
            return ""
        return data.get("task_id", "")

    async def get_report_status(self, task_id: str) -> dict[str, Any]:
        """POST /api/report/generate/status"""
        resp = await self._client.post(
            "/api/report/generate/status",
            json={"task_id": task_id},
        )
        resp.raise_for_status()
        body = resp.json()
        return body.get("data", body)

    async def get_report_by_simulation(self, simulation_id: str) -> dict[str, Any]:
        """GET /api/report/by-simulation/{simulation_id}"""
        resp = await self._client.get(
            f"/api/report/by-simulation/{simulation_id}"
        )
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
        resp = await self._client.get(
            f"/api/simulation/{simulation_id}/actions",
            params={"platform": platform, "limit": limit, "offset": offset},
        )
        resp.raise_for_status()
        body = resp.json()
        return body.get("data", body)

    async def get_simulation_posts(
        self, simulation_id: str, platform: str = "twitter", limit: int = 100
    ) -> dict[str, Any]:
        """GET /api/simulation/{id}/posts"""
        resp = await self._client.get(
            f"/api/simulation/{simulation_id}/posts",
            params={"platform": platform, "limit": limit},
        )
        resp.raise_for_status()
        body = resp.json()
        return body.get("data", body)

    # ------------------------------------------------------------------
    # Realtime monitoring
    # ------------------------------------------------------------------

    async def get_graph_data(self, graph_id: str) -> dict[str, Any]:
        """GET /api/graph/data/{graph_id} — 그래프 노드+엣지 데이터."""
        resp = await self._client.get(f"/api/graph/data/{graph_id}")
        resp.raise_for_status()
        body = resp.json()
        return body.get("data", body)

    async def get_agent_stats(self, simulation_id: str) -> dict[str, Any]:
        """GET /api/simulation/{id}/agent-stats — 에이전트 활동 통계."""
        resp = await self._client.get(f"/api/simulation/{simulation_id}/agent-stats")
        resp.raise_for_status()
        body = resp.json()
        return body.get("data", body)

    async def get_profiles_realtime(self, simulation_id: str, platform: str = "twitter") -> dict[str, Any]:
        """GET /api/simulation/{id}/profiles/realtime — 프로필 생성 실시간 진행."""
        resp = await self._client.get(
            f"/api/simulation/{simulation_id}/profiles/realtime",
            params={"platform": platform},
        )
        resp.raise_for_status()
        body = resp.json()
        return body.get("data", body)

    async def get_config_realtime(self, simulation_id: str) -> dict[str, Any]:
        """GET /api/simulation/{id}/config/realtime — 설정 생성 실시간 진행."""
        resp = await self._client.get(f"/api/simulation/{simulation_id}/config/realtime")
        resp.raise_for_status()
        body = resp.json()
        return body.get("data", body)

    # ------------------------------------------------------------------
    # 폴링 유틸리티
    # ------------------------------------------------------------------

    async def poll_until_done(
        self,
        poll_fn,
        interval: float = 5.0,
        timeout: float = 600.0,
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
        while elapsed < timeout:
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
            resp = await self._client.get("/api/graph/project/list", timeout=5.0)
            return resp.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException):
            return False

    async def close(self) -> None:
        await self._client.aclose()
