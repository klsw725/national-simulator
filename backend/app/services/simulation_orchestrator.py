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

import uuid

from app.clients.mirofish import MiroFishClient
from app.database import get_pool
from app.geopolitics.actors import GeopoliticalActorState
from app.geopolitics.engine import DecisionEngine
from app.geopolitics.events import GeopoliticsEvent
from app.models.scenario import GeopoliticsMode, SimulationParams
from app.ontology.versioning import OntologyVersioning
from app.services.action_logger import ActionLogger
from app.services.geopolitics_interactive import (
    build_actor_response_options,
    build_direction_options,
    create_geopolitics_decision_point,
    find_trigger_event,
    link_snapshot_to_dp,
    save_geopolitics_snapshot,
    should_pause,
)
from app.services.geopolitics_mapper import GEOPOLITICS_ACTION_MAP, map_actions_to_geopolitics
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

【필수 행동 규칙】
- 각 행위자는 시뮬레이션 전체에서 최소 1회 이상 공식 성명(CREATE_POST) 또는 공식 반응(QUOTE_POST)을 반드시 수행해야 합니다.
- DO_NOTHING은 해당 라운드에서 이미 다른 적극적 행동을 수행한 뒤에만 선택할 수 있습니다. 첫 행동으로 DO_NOTHING을 선택하는 것은 금지됩니다.
- 현실 세계에서 해상 긴장 상황이 발생하면 관련 국가들은 반드시 공식 입장을 표명합니다. 완전한 침묵은 비현실적입니다.
- 국제기구(UN, ASEAN 등)는 최소한 "상황을 주시하고 있다"는 성명을 발표해야 합니다.
- 강대국(Superpower)과 지역 강국(RegionalPower)은 적극적 행동(CREATE_POST, QUOTE_POST)의 비율이 전체 행동의 50% 이상이어야 합니다.
"""

from app.config import settings

GRAPH_BUILD_TIMEOUT = settings.graph_build_timeout
PREPARE_TIMEOUT = settings.prepare_timeout
RUN_TIMEOUT = settings.run_timeout
REPORT_TIMEOUT = settings.report_timeout
POLL_INTERVAL = settings.poll_interval


class SimulationOrchestrator:
    def __init__(self, mf_client: MiroFishClient, sb_client=None):
        self.mf = mf_client
        self.sb_client = sb_client

    async def _step_ontology(
        self,
        scenario_id: str,
        result_id: str,
        seed_text: str,
        simulation_params: SimulationParams | None = None,
    ) -> dict:
        """Step 1: Ontology generation. Returns ontology_result with project_id."""
        await self._update_status(scenario_id, result_id, "simulating:ontology")
        logger.info("[%s] Step 1: Ontology generation", scenario_id)

        requirement = SIMULATION_REQUIREMENT
        if simulation_params and simulation_params.simulation_requirement:
            requirement = simulation_params.simulation_requirement

        ontology_result = await self.mf.generate_ontology(
            seed_text=seed_text,
            seed_filename="seed_document.md",
            simulation_requirement=requirement,
            project_name=f"osint-{scenario_id}",
        )
        project_id = ontology_result.get("project_id", "")
        logger.info("[%s] Ontology done → project_id=%s", scenario_id, project_id)

        await self._update_ids(result_id, project_id=project_id)
        await ActionLogger.log(
            "pipeline.ontology",
            scenario_id,
            payload={"project_id": project_id},
        )
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
        await ActionLogger.log(
            "pipeline.graph_build",
            scenario_id,
            payload={"graph_id": graph_id},
        )

    async def _step_create_prepare(
        self,
        scenario_id: str,
        result_id: str,
        project_id: str,
        simulation_params: SimulationParams | None = None,
    ) -> str:
        """Step 3+4: Simulation create + prepare. Returns mf_simulation_id."""
        await self._update_status(scenario_id, result_id, "simulating:create")
        logger.info("[%s] Step 3: Simulation create", scenario_id)

        platform = simulation_params.platform if simulation_params else "twitter"
        enable_twitter = platform in ("twitter", "parallel")
        enable_reddit = platform in ("reddit", "parallel")

        sim_result = await self.mf.create_simulation(
            project_id,
            enable_twitter=enable_twitter,
            enable_reddit=enable_reddit,
        )
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

        sim_state = await self.mf.get_simulation_state(mf_simulation_id)
        mf_status = sim_state.get("status", "")
        if mf_status != "ready":
            error_msg = sim_state.get("error", f"unexpected status: {mf_status}")
            raise RuntimeError(f"Prepare failed: {error_msg}")

        logger.info("[%s] Prepare done", scenario_id)
        await ActionLogger.log(
            "pipeline.prepare",
            scenario_id,
            payload={"simulation_id": mf_simulation_id},
        )

        return mf_simulation_id

    async def _step_run_simulation(
        self,
        scenario_id: str,
        result_id: str,
        mf_simulation_id: str,
        max_rounds: int,
        simulation_params: SimulationParams | None = None,
    ) -> None:
        """Step 5: Start simulation and poll until done."""
        await self._update_status(scenario_id, result_id, "simulating:running")
        logger.info("[%s] Step 5: Simulation start (max_rounds=%d)", scenario_id, max_rounds)

        platform = simulation_params.platform if simulation_params else "twitter"
        simulation_hours = simulation_params.simulation_hours if simulation_params else None
        tools_enabled = simulation_params.web_search_enabled if simulation_params else False
        geopolitics_enabled = simulation_params.geopolitics_enabled if simulation_params else False

        await self.mf.start_simulation(
            mf_simulation_id,
            platform=platform,
            max_rounds=max_rounds,
            simulation_hours=simulation_hours,
            tools_enabled=tools_enabled,
            geopolitics_enabled=geopolitics_enabled,
        )
        await self.mf.poll_until_done(
            poll_fn=lambda: self.mf.get_run_status(mf_simulation_id),
            timeout=RUN_TIMEOUT,
            interval=POLL_INTERVAL,
            status_key="runner_status",
            done_values=("completed", "stopped"),
        )
        logger.info("[%s] Simulation run done", scenario_id)
        await ActionLogger.log(
            "pipeline.run_complete",
            scenario_id,
            payload={"simulation_id": mf_simulation_id, "max_rounds": max_rounds},
        )

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
        await ActionLogger.log("pipeline.report", scenario_id)

    def _init_geopolitics_engine(self, actions: list[dict]) -> DecisionEngine | None:
        agent_names: dict[str, int] = {}
        for action in actions:
            name = action.get("agent_name", "")
            if name:
                agent_names[name] = agent_names.get(name, 0) + 1

        if not agent_names:
            return None

        engine = DecisionEngine()
        sorted_agents = sorted(agent_names.items(), key=lambda x: x[1], reverse=True)
        for i, (name, _) in enumerate(sorted_agents[:10]):
            actor = GeopoliticalActorState(
                actor_id=name,
                name=name,
                actor_type="state",
                threat_perception=0.3 + (i * 0.05),
                domestic_pressure=0.2,
                resource_level=max(0.3, 0.9 - (i * 0.1)),
                adversaries=[n for n, _ in sorted_agents[:10] if n != name][:3],
                allies=[n for n, _ in sorted_agents[:10] if n != name][3:5],
            )
            engine.add_actor(actor)

        for action in actions:
            raw_type = (action.get("action_type") or "").lower()
            geo_type = GEOPOLITICS_ACTION_MAP.get(raw_type, raw_type)
            agent_name = action.get("agent_name", "")
            if not agent_name or agent_name not in agent_names:
                continue
            targets = [n for n in agent_names if n != agent_name][:2]
            if targets and geo_type in ("diplomatic_statement", "official_response", "alliance_support"):
                event = GeopoliticsEvent(
                    event_type="diplomatic_statement",
                    source_actor_id=agent_name,
                    target_actor_ids=targets,
                    magnitude=0.3,
                    description=f"{agent_name}: {geo_type}",
                )
                engine.apply_event(event)

        return engine

    async def _step_geopolitics_analysis(
        self,
        scenario_id: str,
        result_id: str,
        actions: list[dict],
    ) -> dict[str, Any] | None:
        await self._update_status(scenario_id, result_id, "simulating:geopolitics")
        logger.info("[%s] Step 7: Geopolitics analysis", scenario_id)

        engine = self._init_geopolitics_engine(actions)
        if engine is None:
            logger.warning("[%s] No agents found in actions, skipping geopolitics", scenario_id)
            return None

        geo_result = engine.run_simulation(rounds=3)

        now = datetime.now(timezone.utc).isoformat()
        pool = get_pool()
        async with pool.acquire() as conn:
            for round_data in geo_result.get("timeline", []):
                for event_dict in round_data.get("events", []) + round_data.get("cascade_events", []):
                    event_id = f"ge_{uuid.uuid4().hex[:12]}"
                    await conn.execute(
                        """INSERT INTO geopolitics_events
                           (id, scenario_id, simulation_result_id, action_type, actor_id,
                            target_actor_ids, content, magnitude, round_number, event_at)
                           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)""",
                        event_id, scenario_id, result_id,
                        event_dict.get("event_type", ""),
                        event_dict.get("source_actor_id", ""),
                        json.dumps(event_dict.get("target_actor_ids", [])),
                        event_dict.get("description", ""),
                        event_dict.get("magnitude", 0.5),
                        event_dict.get("round_number", 0),
                        now,
                    )

        logger.info(
            "[%s] Geopolitics analysis done: %d events, %d rounds",
            scenario_id, geo_result.get("total_events", 0), geo_result.get("total_rounds", 0),
        )
        await ActionLogger.log(
            "pipeline.geopolitics",
            scenario_id,
            payload={"total_events": geo_result.get("total_events", 0)},
        )
        return geo_result

    async def _step_geopolitics_interactive(
        self,
        scenario_id: str,
        result_id: str,
        actions: list[dict],
        simulation_params: SimulationParams,
    ) -> dict[str, Any] | None:
        mode = simulation_params.geopolitics_mode
        player_actor_id = simulation_params.geopolitics_player_actor_id
        threshold = simulation_params.geopolitics_pause_threshold
        total_rounds = simulation_params.geopolitics_rounds

        await self._update_status(scenario_id, result_id, "simulating:geopolitics")
        logger.info("[%s] Step 7: Interactive geopolitics (%s mode, %d rounds)", scenario_id, mode.value, total_rounds)

        engine = self._init_geopolitics_engine(actions)
        if engine is None:
            return None

        all_round_results = []
        now = datetime.now(timezone.utc).isoformat()
        pool = get_pool()

        for round_num in range(1, total_rounds + 1):
            round_result = engine.run_single_round()
            all_round_results.append(round_result)

            async with pool.acquire() as conn:
                for event_dict in round_result.get("events", []) + round_result.get("cascade_events", []):
                    event_id = f"ge_{uuid.uuid4().hex[:12]}"
                    await conn.execute(
                        """INSERT INTO geopolitics_events
                           (id, scenario_id, simulation_result_id, action_type, actor_id,
                            target_actor_ids, content, magnitude, round_number, event_at)
                           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)""",
                        event_id, scenario_id, result_id,
                        event_dict.get("event_type", ""),
                        event_dict.get("source_actor_id", ""),
                        json.dumps(event_dict.get("target_actor_ids", [])),
                        event_dict.get("description", ""),
                        event_dict.get("magnitude", 0.5),
                        event_dict.get("round_number", 0),
                        now,
                    )

            if should_pause(round_result, mode, player_actor_id, threshold):
                snapshot_id = await save_geopolitics_snapshot(
                    scenario_id, result_id, round_num, engine, mode, player_actor_id,
                )

                if mode == GeopoliticsMode.ACTOR_ROLE and player_actor_id:
                    trigger_event = find_trigger_event(round_result, player_actor_id)
                    options = build_actor_response_options(engine, player_actor_id, trigger_event or {})
                    dp_type = "geopolitics_actor_response"
                    recommended = next((o["id"] for o in options if o.get("data", {}).get("engine_recommended")), options[0]["id"])
                else:
                    options = build_direction_options(round_result)
                    dp_type = "geopolitics_direction"
                    recommended = "maintain"

                dp_id = await create_geopolitics_decision_point(
                    scenario_id, dp_type, options, recommended,
                )
                await link_snapshot_to_dp(snapshot_id, dp_id)
                await self._update_status(scenario_id, result_id, "simulating:geopolitics_paused")

                logger.info("[%s] Geopolitics paused at round %d (dp=%s)", scenario_id, round_num, dp_id)
                await ActionLogger.log(
                    "pipeline.geopolitics.paused", scenario_id,
                    payload={"round": round_num, "decision_point_id": dp_id, "mode": mode.value},
                )
                return {"status": "paused", "round": round_num, "decision_point_id": dp_id}

        logger.info("[%s] Interactive geopolitics done: %d rounds", scenario_id, total_rounds)
        await ActionLogger.log(
            "pipeline.geopolitics", scenario_id,
            payload={"total_events": sum(len(r.get("events", [])) for r in all_round_results)},
        )
        return {
            "total_rounds": total_rounds,
            "timeline": all_round_results,
            "final_states": {a.actor_id: a.to_dict() for a in engine.get_all_actors()},
            "total_events": len(engine.get_event_log()),
        }

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
        simulation_params: SimulationParams | None = None,
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
                    simulation_params=simulation_params,
                )
                await self._register_ontology_version(scenario_id, result_id, ontology_result)
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
                    simulation_params=simulation_params,
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
                platform = simulation_params.platform if simulation_params else "twitter"
                await self._save_checkpoint_data(
                    result_id,
                    {"max_rounds": max_rounds, "platform": platform},
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
                    simulation_params=simulation_params,
                )
                await self._step_report(scenario_id, result_id, mf_simulation_id)
                await self._collect_and_store_results(
                    result_id,
                    mf_simulation_id,
                    simulation_params=simulation_params,
                )
                return

        except Exception as exc:
            logger.exception("[%s] Checkpoint pipeline failed", scenario_id)
            await self._update_status(scenario_id, result_id, "failed")
            try:
                await ActionLogger.log(
                    "pipeline.failed",
                    scenario_id,
                    payload={"error": str(exc)[:500]},
                )
            except Exception:
                logger.warning("[%s] Failed to log checkpoint pipeline error", scenario_id, exc_info=True)

    async def run_pipeline(
        self,
        scenario_id: str,
        result_id: str,
        seed_text: str,
        max_rounds: int,
        simulation_params: SimulationParams | None = None,
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
                simulation_params=simulation_params,
            )
            await self._register_ontology_version(scenario_id, result_id, ontology_result)
            project_id = ontology_result.get("project_id", "")
            await self._step_graph_build(scenario_id, result_id, project_id)
            mf_simulation_id = await self._step_create_prepare(
                scenario_id,
                result_id,
                project_id,
                simulation_params=simulation_params,
            )
            await self._step_run_simulation(
                scenario_id,
                result_id,
                mf_simulation_id,
                max_rounds,
                simulation_params=simulation_params,
            )
            await self._step_report(scenario_id, result_id, mf_simulation_id)

            await self._collect_and_store_results(
                result_id,
                mf_simulation_id,
                simulation_params=simulation_params,
            )

        except Exception as exc:
            logger.exception("[%s] Pipeline failed", scenario_id)
            await self._update_status(scenario_id, result_id, "failed")
            try:
                await ActionLogger.log(
                    "pipeline.failed",
                    scenario_id,
                    payload={"error": str(exc)[:500]},
                )
            except Exception:
                logger.warning("[%s] Failed to log pipeline error", scenario_id, exc_info=True)

    @staticmethod
    def _compute_do_nothing_ratio(actions: Any) -> float:
        action_list: list[dict] = []
        if isinstance(actions, dict) and isinstance(actions.get("actions"), list):
            action_list = actions["actions"]
        elif isinstance(actions, list):
            action_list = actions
        if not action_list:
            return 1.0
        do_nothing_count = sum(
            1 for a in action_list
            if isinstance(a, dict)
            and (a.get("action_type") or "").lower() in ("do_nothing", "strategic_observation")
        )
        return do_nothing_count / len(action_list)

    async def _collect_and_store_results(
        self,
        result_id: str,
        mf_simulation_id: str,
        simulation_params: SimulationParams | None = None,
    ) -> None:
        """시뮬레이션 결과 수집 → DB 저장."""
        # 액션 로그 + 보고서 수집
        actions = await self.mf.get_simulation_actions(mf_simulation_id)
        if isinstance(actions, dict) and "actions" in actions:
            actions["actions"] = map_actions_to_geopolitics(actions["actions"])
        elif isinstance(actions, list):
            actions = map_actions_to_geopolitics(actions)

        do_nothing_ratio = self._compute_do_nothing_ratio(actions)
        if do_nothing_ratio > 0.7:
            logger.warning(
                "[%s] Sparse simulation detected: DO_NOTHING ratio=%.0f%%. "
                "Report quality may be degraded.",
                result_id, do_nothing_ratio * 100,
            )

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
        if simulation_params and simulation_params.geopolitics_enabled:
            action_list = actions.get("actions", actions) if isinstance(actions, dict) else actions
            if isinstance(action_list, list):
                try:
                    if simulation_params.geopolitics_mode != GeopoliticsMode.AUTO:
                        geo_result = await self._step_geopolitics_interactive(
                            scenario_id, result_id, action_list, simulation_params,
                        )
                        if geo_result and geo_result.get("status") == "paused":
                            return
                    else:
                        await self._step_geopolitics_analysis(scenario_id, result_id, action_list)
                except Exception:
                    logger.warning("[%s] Geopolitics analysis failed, continuing", scenario_id)
                await self._update_status(scenario_id, result_id, "completed")

        try:
            from app.services.causal_log_collector import CausalLogCollector
            collector = CausalLogCollector()
            await collector.collect_from_result(scenario_id, result_id)

            # SCM 자동 적합 시도 (데이터 충분 시)
            df = await collector.build_dataframe(scenario_id, min_results=3)
            if df is not None and len(df) >= 30:
                from app.services.causal_reasoner import CausalReasoner
                from app.causal.domain_dag import build_domain_dag
                reasoner = CausalReasoner()
                dag = build_domain_dag()
                reasoner.fit("domain", dag, df)
                logger.info("[%s] Causal SCM auto-fitted with %d observations", scenario_id, len(df))
        except Exception as exc:
            logger.warning("[%s] Causal log collection/fit failed (non-fatal): %s", scenario_id, exc)

        await ActionLogger.log(
            "pipeline.completed",
            scenario_id,
            payload={"result_id": result_id},
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
            elif status == "completed":
                sim_status = "completed"
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

    async def _register_ontology_version(
        self,
        scenario_id: str,
        result_id: str,
        ontology_result: dict,
    ) -> None:
        schema_json = {
            "entity_types": ontology_result.get("entity_types", []),
            "edge_types": ontology_result.get("edge_types", []),
        }

        if not schema_json["entity_types"] and not schema_json["edge_types"]:
            ontology_data = ontology_result.get("ontology", {})
            if isinstance(ontology_data, dict):
                schema_json = {
                    "entity_types": ontology_data.get("entity_types", []),
                    "edge_types": ontology_data.get("edge_types", []),
                }

        if not schema_json["entity_types"] and not schema_json["edge_types"]:
            logger.warning("[%s] Ontology result has no entity/edge types, skipping version registration", scenario_id)
            return

        now_ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        version_str = f"{scenario_id}-{now_ts}"

        versioning = OntologyVersioning()
        try:
            reg = await versioning.register(
                version=version_str,
                schema_json=schema_json,
                change_summary=f"Auto-registered from simulation pipeline for {scenario_id}",
                created_by="pipeline",
            )
            actual_version = reg.get("version", version_str)
            pool = get_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE simulation_results SET ontology_version = $1 WHERE id = $2",
                    actual_version,
                    result_id,
                )
            logger.info("[%s] Ontology version registered: %s (skipped=%s)", scenario_id, actual_version, reg.get("skipped", False))
        except Exception:
            logger.warning("[%s] Ontology version registration failed, continuing", scenario_id, exc_info=True)

    @staticmethod
    def determine_recovery_point(row) -> str:
        if not row["mirofish_project_id"]:
            return "ontology"
        if not row["graph_id"]:
            return "graph_build"
        if not row["mirofish_simulation_id"]:
            return "create_prepare"
        return "run_simulation"

    async def run_from_failure(
        self,
        scenario_id: str,
        result_id: str,
        seed_text: str,
        max_rounds: int,
        recovery_point: str,
        project_id: str = "",
        graph_id: str = "",
        mf_simulation_id: str = "",
        simulation_params: SimulationParams | None = None,
    ) -> None:
        try:
            logger.info(
                "[%s] Retrying from '%s' (project=%s, graph=%s, sim=%s)",
                scenario_id, recovery_point, project_id, graph_id, mf_simulation_id,
            )
            await ActionLogger.log(
                "pipeline.retry",
                scenario_id,
                payload={"recovery_point": recovery_point, "result_id": result_id},
            )

            if recovery_point == "ontology":
                ontology_result = await self._step_ontology(
                    scenario_id, result_id, seed_text, simulation_params=simulation_params,
                )
                await self._register_ontology_version(scenario_id, result_id, ontology_result)
                project_id = ontology_result.get("project_id", "")
                recovery_point = "graph_build"

            if recovery_point == "graph_build":
                await self._step_graph_build(scenario_id, result_id, project_id)
                recovery_point = "create_prepare"

            if recovery_point == "create_prepare":
                mf_simulation_id = await self._step_create_prepare(
                    scenario_id, result_id, project_id, simulation_params=simulation_params,
                )
                recovery_point = "run_simulation"

            if recovery_point == "run_simulation":
                await self._step_run_simulation(
                    scenario_id, result_id, mf_simulation_id,
                    max_rounds, simulation_params=simulation_params,
                )
                await self._step_report(scenario_id, result_id, mf_simulation_id)

            await self._collect_and_store_results(
                result_id, mf_simulation_id, simulation_params=simulation_params,
            )

        except Exception as exc:
            logger.exception("[%s] Retry pipeline failed", scenario_id)
            await self._update_status(scenario_id, result_id, "failed")
            try:
                await ActionLogger.log(
                    "pipeline.retry_failed",
                    scenario_id,
                    payload={"error": str(exc)[:500], "recovery_point": recovery_point},
                )
            except Exception:
                logger.warning("[%s] Failed to log retry error", scenario_id, exc_info=True)
