"""시뮬레이션 파이프라인 오케스트레이터.

MiroFish 6단계 파이프라인을 순차 실행하고 상태를 DB에 기록한다.

Pipeline:
  1. ontology/generate → project_id
  2. graph/build → poll → graph_id
  3. simulation/create → simulation_id
  4. simulation/prepare → poll → profiles ready
  5. simulation/start → poll → completed
  6. report/generate → poll → report ready
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from app.clients.mirofish import MiroFishClient
from app.database import get_pool
from app.services.snapshot_service import SnapshotService

logger = logging.getLogger(__name__)

# MVP-SPEC.md Section 11
SIMULATION_REQUIREMENT = """\
해상 안보 시나리오의 지정학적 시뮬레이션입니다.

이 시뮬레이션에서:
- 각 엔티티는 '국가 행위자' 또는 '국제 기구'입니다.
- 엔티티 간에는 동맹 지지, 비난 성명, 중립 선언 등의 상호작용을 합니다.
- 해상 긴장 상황에서 각 행위자의 반응과 여론 전파 경로를 시뮬레이션합니다.

가능한 엔티티 유형:
- Superpower, RegionalPower, SmallState
- MilitaryAlliance, InternationalOrganization
- MediaOutlet, MilitaryCommander, Diplomat
- Person, Organization

당신은 소셜미디어 플랫폼에서 국가/기관의 공식 계정을 운영합니다.
- 포스트 작성 (CREATE_POST): 공식 성명 또는 입장 발표
- 인용 포스트 (QUOTE_POST): 타국 성명에 대한 공식 반응/논평
- 리포스트 (REPOST): 동맹국 성명 지지/전파
- 좋아요 (LIKE_POST): 타국 성명에 대한 암묵적 동의
- 팔로우 (FOLLOW): 외교적 관계 형성 의사 표시
- 아무것도 안 함 (DO_NOTHING): 전략적 관망/무반응
"""

# 폴링 설정
GRAPH_BUILD_TIMEOUT = 600.0    # 10분
PREPARE_TIMEOUT = 900.0        # 15분
RUN_TIMEOUT = 1800.0           # 30분
REPORT_TIMEOUT = 900.0         # 15분
POLL_INTERVAL = 5.0            # 5초


class SimulationOrchestrator:
    def __init__(self, mf_client: MiroFishClient, sb_client=None):
        self.mf = mf_client
        self.sb_client = sb_client

    async def _step_ontology(
        self,
        scenario_id: str,
        result_id: str,
        seed_text: str,
    ) -> dict:
        """Step 1: Ontology generation. Returns ontology_result with project_id."""
        await self._update_status(scenario_id, result_id, "simulating:ontology")
        logger.info("[%s] Step 1: Ontology generation", scenario_id)

        ontology_result = await self.mf.generate_ontology(
            seed_text=seed_text,
            seed_filename="seed_document.md",
            simulation_requirement=SIMULATION_REQUIREMENT,
            project_name=f"osint-{scenario_id}",
        )
        project_id = ontology_result.get("project_id", "")
        logger.info("[%s] Ontology done → project_id=%s", scenario_id, project_id)

        await self._update_ids(result_id, project_id=project_id)
        return ontology_result

    async def _step_graph_build(
        self,
        scenario_id: str,
        result_id: str,
        project_id: str,
    ) -> None:
        """Step 2: Graph build. Uses project_id from step 1."""
        await self._update_status(scenario_id, result_id, "simulating:graph_build")
        logger.info("[%s] Step 2: Graph build", scenario_id)

        task_id = await self.mf.build_graph(project_id)
        await self._update_ids(result_id, graph_task_id=task_id)

        result = await self.mf.poll_until_done(
            poll_fn=lambda: self.mf.get_task_status(task_id),
            timeout=GRAPH_BUILD_TIMEOUT,
            interval=POLL_INTERVAL,
        )
        graph_id = result.get("result", {}).get("graph_id", "") if isinstance(result.get("result"), dict) else ""
        if graph_id:
            await self._update_ids(result_id, graph_id=graph_id)
        logger.info("[%s] Graph build done (graph_id=%s)", scenario_id, graph_id)

    async def _step_create_prepare(
        self,
        scenario_id: str,
        result_id: str,
        project_id: str,
    ) -> str:
        """Step 3+4: Simulation create + prepare. Returns mf_simulation_id."""
        await self._update_status(scenario_id, result_id, "simulating:create")
        logger.info("[%s] Step 3: Simulation create", scenario_id)

        sim_result = await self.mf.create_simulation(project_id)
        mf_simulation_id = sim_result.get("simulation_id", "")
        logger.info("[%s] Simulation created → id=%s", scenario_id, mf_simulation_id)

        await self._update_ids(result_id, mf_simulation_id=mf_simulation_id)

        await self._update_status(scenario_id, result_id, "simulating:prepare")
        logger.info("[%s] Step 4: Simulation prepare", scenario_id)

        prepare_task_id = await self.mf.prepare_simulation(mf_simulation_id)
        if prepare_task_id:
            await self.mf.poll_until_done(
                poll_fn=lambda: self.mf.get_prepare_status(prepare_task_id),
                timeout=PREPARE_TIMEOUT,
                interval=POLL_INTERVAL,
            )
        logger.info("[%s] Prepare done", scenario_id)

        return mf_simulation_id

    async def _step_run_simulation(
        self,
        scenario_id: str,
        result_id: str,
        mf_simulation_id: str,
        max_rounds: int,
    ) -> None:
        """Step 5: Start simulation and poll until done."""
        await self._update_status(scenario_id, result_id, "simulating:running")
        logger.info("[%s] Step 5: Simulation start (max_rounds=%d)", scenario_id, max_rounds)

        await self.mf.start_simulation(
            mf_simulation_id, platform="twitter", max_rounds=max_rounds,
        )
        await self.mf.poll_until_done(
            poll_fn=lambda: self.mf.get_run_status(mf_simulation_id),
            timeout=RUN_TIMEOUT,
            interval=POLL_INTERVAL,
            status_key="runner_status",
            done_values=("completed", "stopped"),
        )
        logger.info("[%s] Simulation run done", scenario_id)

    async def _step_report(
        self,
        scenario_id: str,
        result_id: str,
        mf_simulation_id: str,
    ) -> None:
        """Step 6: Generate report and poll until done."""
        await self._update_status(scenario_id, result_id, "simulating:report")
        logger.info("[%s] Step 6: Report generation", scenario_id)

        report_task_id = await self.mf.generate_report(mf_simulation_id)
        if report_task_id:
            await self.mf.poll_until_done(
                poll_fn=lambda: self.mf.get_report_status(report_task_id),
                timeout=REPORT_TIMEOUT,
                interval=POLL_INTERVAL,
            )
        logger.info("[%s] Report done", scenario_id)

    async def _save_checkpoint_data(self, result_id: str, data: dict) -> None:
        """Save intermediate result JSON to checkpoint_data column."""
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE simulation_results SET checkpoint_data = $1 WHERE id = $2",
                json.dumps(data, ensure_ascii=False),
                result_id,
            )

    async def _get_checkpoint_info(self, result_id: str) -> dict:
        """Read current status, checkpoint_data, and MiroFish IDs from DB."""
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT status, checkpoint_data, mirofish_project_id, mirofish_simulation_id FROM simulation_results WHERE id = $1",
                result_id,
            )
        if not row:
            raise ValueError(f"Simulation result not found: {result_id}")

        raw = row["checkpoint_data"] or "{}"
        checkpoint_data: dict[str, Any] = {}
        if isinstance(raw, str):
            checkpoint_data = json.loads(raw)
        elif isinstance(raw, dict):
            checkpoint_data = raw

        return {
            "status": row["status"] or "",
            "checkpoint_data": checkpoint_data,
            "mirofish_project_id": row["mirofish_project_id"] or "",
            "mirofish_simulation_id": row["mirofish_simulation_id"] or "",
        }

    async def _apply_edits(
        self,
        result_id: str,
        current_status: str,
        edits: dict,
    ) -> None:
        """Apply user edits based on checkpoint type.
        - checkpoint:seed → update seed text in seeds table
        - checkpoint:config → update max_rounds in scenarios table
        """
        if not edits:
            return

        pool = get_pool()
        async with pool.acquire() as conn:
            if current_status == "checkpoint:seed" and (
                "seed_text" in edits or "text" in edits
            ):
                seed_text = edits.get("seed_text", edits.get("text", ""))
                row = await conn.fetchrow(
                    "SELECT scenario_id FROM simulation_results WHERE id = $1",
                    result_id,
                )
                if row and row["scenario_id"]:
                    scenario_id = row["scenario_id"]
                    await conn.execute(
                        """UPDATE seeds
                           SET text = $1
                           WHERE scenario_id = $2
                             AND id = (
                                 SELECT id FROM seeds
                                  WHERE scenario_id = $3
                                  ORDER BY created_at DESC
                                  LIMIT 1
                              )""",
                        seed_text,
                        scenario_id,
                        scenario_id,
                    )

            if current_status == "checkpoint:config" and "max_rounds" in edits:
                row = await conn.fetchrow(
                    "SELECT scenario_id FROM simulation_results WHERE id = $1",
                    result_id,
                )
                if row and row["scenario_id"]:
                    await conn.execute(
                        "UPDATE scenarios SET max_rounds = $1 WHERE id = $2",
                        int(edits["max_rounds"]),
                        row["scenario_id"],
                    )

    async def run_from_checkpoint(
        self,
        scenario_id: str,
        result_id: str,
        max_rounds: int,
        edits: dict | None = None,
    ) -> None:
        """Execute next pipeline step from current checkpoint status.

        Called by POST /continue endpoint as BackgroundTask.
        Reads current status from DB, determines next step, executes it,
        then pauses at next checkpoint (saves checkpoint_data, updates status).

        If this is the last segment (run+report), runs to completion.
        """
        try:
            checkpoint_info = await self._get_checkpoint_info(result_id)
            current_status = checkpoint_info["status"]
            checkpoint_data = checkpoint_info.get("checkpoint_data", {})
            project_id = checkpoint_info.get("mirofish_project_id", "")
            mf_simulation_id = checkpoint_info.get("mirofish_simulation_id", "")

            if edits:
                await self._apply_edits(result_id, current_status, edits)
                if current_status == "checkpoint:config" and "max_rounds" in edits:
                    max_rounds = int(edits["max_rounds"])

            if current_status == "checkpoint:seed":
                if self.sb_client:
                    try:
                        snapshot_svc = SnapshotService(self.sb_client)
                        existing = await snapshot_svc.get_snapshot_metadata(scenario_id)
                        if not existing:
                            pool = get_pool()
                            async with pool.acquire() as conn:
                                scn_row = await conn.fetchrow(
                                    "SELECT region_bbox FROM scenarios WHERE id = $1",
                                    scenario_id,
                                )
                            bbox = (
                                json.loads(scn_row["region_bbox"])
                                if scn_row and scn_row["region_bbox"]
                                else None
                            )
                            await snapshot_svc.create_snapshot(scenario_id, bbox)
                            logger.info("[%s] OSINT snapshot saved (checkpoint mode)", scenario_id)
                    except Exception:
                        logger.warning("[%s] Snapshot creation failed, continuing", scenario_id)

                pool = get_pool()
                async with pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT text FROM seeds WHERE scenario_id = $1 ORDER BY created_at DESC LIMIT 1",
                        scenario_id,
                    )
                seed_text = row["text"] if row and row["text"] else ""
                ontology_result = await self._step_ontology(
                    scenario_id,
                    result_id,
                    seed_text,
                )
                await self._save_checkpoint_data(
                    result_id,
                    {"ontology": ontology_result},
                )
                await self._update_status(
                    scenario_id,
                    result_id,
                    "checkpoint:ontology",
                )
                return

            if current_status == "checkpoint:ontology":
                if not project_id:
                    project_id = checkpoint_data.get("ontology", {}).get("project_id", "")
                await self._step_graph_build(scenario_id, result_id, project_id)
                await self._save_checkpoint_data(
                    result_id,
                    {"step": "graph_build"},
                )
                await self._update_status(scenario_id, result_id, "checkpoint:graph")
                return

            if current_status == "checkpoint:graph":
                mf_simulation_id = await self._step_create_prepare(
                    scenario_id,
                    result_id,
                    project_id,
                )
                await self._save_checkpoint_data(
                    result_id,
                    {"mf_simulation_id": mf_simulation_id},
                )
                await self._update_status(
                    scenario_id,
                    result_id,
                    "checkpoint:profiles",
                )
                return

            if current_status == "checkpoint:profiles":
                await self._save_checkpoint_data(
                    result_id,
                    {"max_rounds": max_rounds, "platform": "twitter"},
                )
                await self._update_status(scenario_id, result_id, "checkpoint:config")
                return

            if current_status == "checkpoint:config":
                if not mf_simulation_id:
                    mf_simulation_id = checkpoint_data.get("mf_simulation_id", "")
                await self._step_run_simulation(
                    scenario_id,
                    result_id,
                    mf_simulation_id,
                    max_rounds,
                )
                await self._step_report(scenario_id, result_id, mf_simulation_id)
                await self._collect_and_store_results(
                    result_id,
                    mf_simulation_id,
                )
                return

        except Exception:
            logger.exception("[%s] Checkpoint pipeline failed", scenario_id)
            await self._update_status(scenario_id, result_id, "failed")

    async def run_pipeline(
        self,
        scenario_id: str,
        result_id: str,
        seed_text: str,
        max_rounds: int,
    ) -> None:
        """전체 파이프라인 실행 (BackgroundTask에서 호출).

        각 단계 완료 후 DB에 상태를 업데이트한다.
        실패 시 status='failed'로 업데이트하고 종료한다.
        """
        try:
            if self.sb_client:
                try:
                    snapshot_svc = SnapshotService(self.sb_client)
                    pool = get_pool()
                    async with pool.acquire() as conn:
                        scn_row = await conn.fetchrow(
                            "SELECT region_bbox FROM scenarios WHERE id = $1",
                            scenario_id,
                        )
                    bbox = (
                        json.loads(scn_row["region_bbox"])
                        if scn_row and scn_row["region_bbox"]
                        else None
                    )
                    await snapshot_svc.create_snapshot(scenario_id, bbox)
                    logger.info("[%s] OSINT snapshot saved", scenario_id)
                except Exception:
                    logger.warning("[%s] Snapshot creation failed, continuing", scenario_id)

            ontology_result = await self._step_ontology(
                scenario_id,
                result_id,
                seed_text,
            )
            project_id = ontology_result.get("project_id", "")
            await self._step_graph_build(scenario_id, result_id, project_id)
            mf_simulation_id = await self._step_create_prepare(
                scenario_id,
                result_id,
                project_id,
            )
            await self._step_run_simulation(
                scenario_id,
                result_id,
                mf_simulation_id,
                max_rounds,
            )
            await self._step_report(scenario_id, result_id, mf_simulation_id)

            # 결과 수집 + DB 저장
            await self._collect_and_store_results(
                result_id,
                mf_simulation_id,
            )

        except Exception:
            logger.exception("[%s] Pipeline failed", scenario_id)
            await self._update_status(scenario_id, result_id, "failed")

    async def _collect_and_store_results(
        self,
        result_id: str,
        mf_simulation_id: str,
    ) -> None:
        """시뮬레이션 결과 수집 → DB 저장."""
        # 액션 로그 + 보고서 수집
        actions = await self.mf.get_simulation_actions(mf_simulation_id)
        report_data = {}
        try:
            report_data = await self.mf.get_report_by_simulation(mf_simulation_id)
        except Exception:
            logger.warning("[%s] Report retrieval failed, skipping", result_id)

        now = datetime.now(timezone.utc).isoformat()
        results_json = json.dumps(actions, ensure_ascii=False)
        report_text = report_data.get("markdown_content", "")

        pool = get_pool()
        async with pool.acquire() as conn:
            scenario_row = await conn.fetchrow(
                "SELECT scenario_id FROM simulation_results WHERE id = $1",
                result_id,
            )
            if not scenario_row:
                raise ValueError(f"Simulation result not found: {result_id}")
            scenario_id = scenario_row["scenario_id"]

            await conn.execute(
                """UPDATE simulation_results
                   SET status = 'completed', results = $1, report = $2, completed_at = $3
                   WHERE id = $4""",
                results_json,
                report_text,
                now,
                result_id,
            )
            await conn.execute(
                """UPDATE scenarios
                   SET simulation_status = 'completed', status = 'completed', updated_at = $1
                   WHERE id = $2""",
                now,
                scenario_id,
            )

        logger.info("[%s] Pipeline completed successfully", scenario_id)

    async def _update_status(
        self,
        scenario_id: str,
        result_id: str,
        status: str,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE simulation_results SET status = $1 WHERE id = $2",
                status,
                result_id,
            )
            if status == "failed":
                sim_status = "failed"
            elif status.startswith("checkpoint:"):
                sim_status = "checkpoint"
            else:
                sim_status = "simulating"
            await conn.execute(
                "UPDATE scenarios SET simulation_status = $1, status = $2, updated_at = $3 WHERE id = $4",
                sim_status,
                sim_status,
                now,
                scenario_id,
            )

    async def _update_ids(
        self,
        result_id: str,
        project_id: str | None = None,
        mf_simulation_id: str | None = None,
        graph_task_id: str | None = None,
        graph_id: str | None = None,
    ) -> None:
        pool = get_pool()
        async with pool.acquire() as conn:
            if project_id:
                await conn.execute(
                    "UPDATE simulation_results SET mirofish_project_id = $1 WHERE id = $2",
                    project_id,
                    result_id,
                )
            if mf_simulation_id:
                await conn.execute(
                    "UPDATE simulation_results SET mirofish_simulation_id = $1 WHERE id = $2",
                    mf_simulation_id,
                    result_id,
                )
            if graph_task_id:
                await conn.execute(
                    "UPDATE simulation_results SET graph_task_id = $1 WHERE id = $2",
                    graph_task_id,
                    result_id,
                )
            if graph_id:
                await conn.execute(
                    "UPDATE simulation_results SET graph_id = $1 WHERE id = $2",
                    graph_id,
                    result_id,
                )
