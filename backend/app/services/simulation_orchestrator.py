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

import aiosqlite

from app.clients.mirofish import MiroFishClient

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
    def __init__(self, mf_client: MiroFishClient):
        self.mf = mf_client

    async def run_pipeline(
        self,
        scenario_id: str,
        result_id: str,
        seed_text: str,
        max_rounds: int,
        db_path: str,
    ) -> None:
        """전체 파이프라인 실행 (BackgroundTask에서 호출).

        각 단계 완료 후 DB에 상태를 업데이트한다.
        실패 시 status='failed'로 업데이트하고 종료한다.
        """
        try:
            # Step 1: 온톨로지 생성
            await self._update_status(db_path, scenario_id, result_id, "simulating:ontology")
            logger.info("[%s] Step 1: Ontology generation", scenario_id)

            ontology_result = await self.mf.generate_ontology(
                seed_text=seed_text,
                seed_filename="seed_document.md",
                simulation_requirement=SIMULATION_REQUIREMENT,
                project_name=f"osint-{scenario_id}",
            )
            project_id = ontology_result.get("project_id", "")
            logger.info("[%s] Ontology done → project_id=%s", scenario_id, project_id)

            await self._update_ids(db_path, result_id, project_id=project_id)

            # Step 2: 그래프 빌드
            await self._update_status(db_path, scenario_id, result_id, "simulating:graph_build")
            logger.info("[%s] Step 2: Graph build", scenario_id)

            task_id = await self.mf.build_graph(project_id)
            await self.mf.poll_until_done(
                poll_fn=lambda: self.mf.get_task_status(task_id),
                timeout=GRAPH_BUILD_TIMEOUT,
                interval=POLL_INTERVAL,
            )
            logger.info("[%s] Graph build done", scenario_id)

            # Step 3: 시뮬레이션 생성
            await self._update_status(db_path, scenario_id, result_id, "simulating:create")
            logger.info("[%s] Step 3: Simulation create", scenario_id)

            sim_result = await self.mf.create_simulation(project_id)
            mf_simulation_id = sim_result.get("simulation_id", "")
            logger.info("[%s] Simulation created → id=%s", scenario_id, mf_simulation_id)

            await self._update_ids(db_path, result_id, mf_simulation_id=mf_simulation_id)

            # Step 4: 시뮬레이션 준비 (프로필 생성 포함)
            await self._update_status(db_path, scenario_id, result_id, "simulating:prepare")
            logger.info("[%s] Step 4: Simulation prepare", scenario_id)

            prepare_task_id = await self.mf.prepare_simulation(mf_simulation_id)
            if prepare_task_id:
                await self.mf.poll_until_done(
                    poll_fn=lambda: self.mf.get_prepare_status(prepare_task_id),
                    timeout=PREPARE_TIMEOUT,
                    interval=POLL_INTERVAL,
                )
            logger.info("[%s] Prepare done", scenario_id)

            # Step 5: 시뮬레이션 실행
            await self._update_status(db_path, scenario_id, result_id, "simulating:running")
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

            # Step 6: 보고서 생성
            await self._update_status(db_path, scenario_id, result_id, "simulating:report")
            logger.info("[%s] Step 6: Report generation", scenario_id)

            report_task_id = await self.mf.generate_report(mf_simulation_id)
            if report_task_id:
                await self.mf.poll_until_done(
                    poll_fn=lambda: self.mf.get_report_status(report_task_id),
                    timeout=REPORT_TIMEOUT,
                    interval=POLL_INTERVAL,
                )
            logger.info("[%s] Report done", scenario_id)

            # 결과 수집 + DB 저장
            await self._collect_and_store_results(
                db_path, scenario_id, result_id, mf_simulation_id,
            )

        except Exception:
            logger.exception("[%s] Pipeline failed", scenario_id)
            await self._update_status(db_path, scenario_id, result_id, "failed")

    async def _collect_and_store_results(
        self,
        db_path: str,
        scenario_id: str,
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
            logger.warning("[%s] Report retrieval failed, skipping", scenario_id)

        now = datetime.now(timezone.utc).isoformat()
        results_json = json.dumps(actions, ensure_ascii=False)
        report_text = report_data.get("markdown_content", "")

        db = await aiosqlite.connect(db_path)
        try:
            await db.execute(
                """UPDATE simulation_results
                   SET status = 'completed', results = ?, report = ?, completed_at = ?
                   WHERE id = ?""",
                (results_json, report_text, now, result_id),
            )
            await db.execute(
                """UPDATE scenarios
                   SET simulation_status = 'completed', status = 'completed', updated_at = ?
                   WHERE id = ?""",
                (now, scenario_id),
            )
            await db.commit()
        finally:
            await db.close()

        logger.info("[%s] Pipeline completed successfully", scenario_id)

    async def _update_status(
        self,
        db_path: str,
        scenario_id: str,
        result_id: str,
        status: str,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        db = await aiosqlite.connect(db_path)
        try:
            await db.execute(
                "UPDATE simulation_results SET status = ? WHERE id = ?",
                (status, result_id),
            )
            sim_status = "failed" if status == "failed" else "simulating"
            await db.execute(
                "UPDATE scenarios SET simulation_status = ?, status = ?, updated_at = ? WHERE id = ?",
                (sim_status, sim_status, now, scenario_id),
            )
            await db.commit()
        finally:
            await db.close()

    async def _update_ids(
        self,
        db_path: str,
        result_id: str,
        project_id: str | None = None,
        mf_simulation_id: str | None = None,
    ) -> None:
        db = await aiosqlite.connect(db_path)
        try:
            if project_id:
                await db.execute(
                    "UPDATE simulation_results SET mirofish_project_id = ? WHERE id = ?",
                    (project_id, result_id),
                )
            if mf_simulation_id:
                await db.execute(
                    "UPDATE simulation_results SET mirofish_simulation_id = ? WHERE id = ?",
                    (mf_simulation_id, result_id),
                )
            await db.commit()
        finally:
            await db.close()
