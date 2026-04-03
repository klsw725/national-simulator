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

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
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
from app.services.context_injection import build_inject_context
from app.services.event_bus import event_bus
from app.services.geopolitics_interactive import (
    build_actor_response_options,
    build_direction_options,
    create_geopolitics_decision_point,
    find_trigger_event,
    get_latest_snapshot,
    link_snapshot_to_dp,
    save_geopolitics_snapshot,
    should_pause,
)
from app.services.geopolitics_mapper import GEOPOLITICS_ACTION_MAP, map_actions_to_geopolitics
from app.services.snapshot_service import SnapshotService

logger = logging.getLogger(__name__)

# MVP-SPEC.md Section 11
SIMULATION_REQUIREMENT = """\
지정학적 시뮬레이션입니다.

이 시뮬레이션에서:
- 각 엔티티는 '국가 행위자' 또는 '국제 기구'입니다.
- 엔티티 간에는 동맹 지지, 비난 성명, 중립 선언 등의 상호작용을 합니다.
- 지정학적 긴장 상황에서 각 행위자의 반응과 여론 전파 경로를 시뮬레이션합니다.

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
- 현실 세계에서 지정학적 긴장 상황이 발생하면 관련 국가들은 반드시 공식 입장을 표명합니다. 완전한 침묵은 비현실적입니다.
- 국제기구(UN, ASEAN 등)는 최소한 "상황을 주시하고 있다"는 성명을 발표해야 합니다.
- 강대국(Superpower)과 지역 강국(RegionalPower)은 적극적 행동(CREATE_POST, QUOTE_POST)의 비율이 전체 행동의 50% 이상이어야 합니다.

【시뮬레이션 설정 생성 규칙 (config 생성 LLM 필수 준수)】
- activity_level: 모든 에이전트의 activity_level은 최소 0.5 이상이어야 합니다. 0.5 미만은 에이전트가 사실상 비활성화됩니다.
- posts_per_hour: 최소 0.3 이상으로 설정하세요.
- off_peak_activity_multiplier: 최소 0.2 이상이어야 합니다. 0.05와 같은 극단적으로 낮은 값은 해당 시간대의 활동을 완전히 소멸시킵니다.
- 시뮬레이션 전체에서 에이전트의 최소 50%가 1회 이상 행동해야 합니다.
- 72라운드 기준, 최소 10개 라운드에서 에이전트 활동이 발생해야 합니다.
"""

from app.config import settings

GRAPH_BUILD_TIMEOUT = settings.graph_build_timeout
PREPARE_TIMEOUT = settings.prepare_timeout
RUN_TIMEOUT = settings.run_timeout
REPORT_TIMEOUT = settings.report_timeout
POLL_INTERVAL = settings.poll_interval
HEARTBEAT_INTERVAL_SECONDS = 30


class SimulationOrchestrator:
    _wargame_heartbeat_tasks: dict[str, asyncio.Task] = {}
    _wargame_continue_locks: dict[str, asyncio.Lock] = {}

    def __init__(self, mf_client: MiroFishClient, sb_client=None):
        self.mf = mf_client
        self.sb_client = sb_client

    @classmethod
    def _get_wargame_continue_lock(cls, result_id: str) -> asyncio.Lock:
        lock = cls._wargame_continue_locks.get(result_id)
        if lock is None:
            lock = asyncio.Lock()
            cls._wargame_continue_locks[result_id] = lock
        return lock

    async def _consume_pending_snapshot_decision(
        self,
        scenario_id: str,
        result_id: str,
        expected_decision_point_id: str,
    ) -> dict[str, Any] | None:
        snapshot = await get_latest_snapshot(scenario_id, result_id)
        if not snapshot:
            return None

        pending_dp_id = snapshot.get("pending_decision_point_id")
        if pending_dp_id != expected_decision_point_id:
            return None

        pool = get_pool()
        async with pool.acquire() as conn:
            updated = await conn.fetchrow(
                """UPDATE geopolitics_snapshots
                   SET pending_decision_point_id = NULL
                   WHERE id = $1 AND pending_decision_point_id = $2
                   RETURNING *""",
                snapshot["id"],
                expected_decision_point_id,
            )

        return dict(updated) if updated else None

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

        await self._clamp_simulation_config(scenario_id, mf_simulation_id)

        await ActionLogger.log(
            "pipeline.prepare",
            scenario_id,
            payload={"simulation_id": mf_simulation_id},
        )

        return mf_simulation_id

    MIN_ACTIVITY_LEVEL = 0.5
    MIN_POSTS_PER_HOUR = 0.3
    MIN_OFF_PEAK_MULTIPLIER = 0.2

    async def _clamp_simulation_config(self, scenario_id: str, mf_simulation_id: str) -> None:
        try:
            config = await self.mf.get_simulation_config(mf_simulation_id)
        except Exception as e:
            logger.warning("[%s] Config fetch failed, skipping clamp: %s", scenario_id, e)
            return

        patched = False
        patch: dict[str, Any] = {}

        time_config = config.get("time_config", {})
        time_patch: dict[str, Any] = {}
        if (time_config.get("off_peak_activity_multiplier") or 0) < self.MIN_OFF_PEAK_MULTIPLIER:
            time_patch["off_peak_activity_multiplier"] = self.MIN_OFF_PEAK_MULTIPLIER
            patched = True

        if time_patch:
            patch["time_config"] = time_patch

        agent_configs = config.get("agent_configs", [])
        clamped_agents = []
        for agent in agent_configs:
            changed = False
            if (agent.get("activity_level") or 0) < self.MIN_ACTIVITY_LEVEL:
                agent["activity_level"] = self.MIN_ACTIVITY_LEVEL
                changed = True
            if (agent.get("posts_per_hour") or 0) < self.MIN_POSTS_PER_HOUR:
                agent["posts_per_hour"] = self.MIN_POSTS_PER_HOUR
                changed = True
            clamped_agents.append(agent)
            if changed:
                patched = True

        if patched:
            patch["agent_configs"] = clamped_agents
            logger.info("[%s] Clamping simulation config: low activity values detected", scenario_id)
            try:
                await self.mf.patch_simulation_config(mf_simulation_id, patch)
                logger.info("[%s] Config clamped successfully", scenario_id)
            except Exception as e:
                logger.warning("[%s] Config clamp failed: %s", scenario_id, e)

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

    async def _emit_sse(self, scenario_id: str, event_type: str, data: dict[str, Any]) -> None:
        await event_bus.emit(scenario_id, {"type": event_type, "data": data})

    async def _start_wargame_process(
        self,
        mf_simulation_id: str,
        max_rounds: int,
        simulation_params: SimulationParams,
    ) -> dict[str, Any]:
        ready_signal = await self.mf.start_round_control(
            simulation_id=mf_simulation_id,
            platform=simulation_params.platform,
            max_rounds=max_rounds,
            tools_enabled=simulation_params.web_search_enabled,
            geopolitics_enabled=simulation_params.geopolitics_enabled,
        )
        return ready_signal

    async def _send_control_signal(
        self,
        mf_simulation_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        signal_type = payload.get("type")
        if signal_type == "proceed":
            return await self.mf.proceed_round(
                mf_simulation_id,
                round_num=int(payload.get("round", 1)),
                inject_context=payload.get("inject_context"),
            )
        if signal_type == "stop":
            return await self.mf.stop_round_control(
                mf_simulation_id,
                reason=str(payload.get("reason", "completed")),
            )
        if signal_type == "heartbeat":
            return await self.mf.heartbeat_round_control(
                mf_simulation_id,
                timestamp=str(payload.get("timestamp", "")),
            )
        raise ValueError(f"unknown wargame control signal type: {signal_type}")

    async def _read_control_signal(self, signal: dict[str, Any]) -> dict[str, Any]:
        return signal

    async def _save_round_actions(
        self,
        scenario_id: str,
        round_num: int,
        actions: list[dict[str, Any]],
    ) -> None:
        await ActionLogger.log(
            "wargame.round_actions",
            scenario_id,
            payload={"round": round_num, "actions_count": len(actions), "actions": actions},
        )

    async def _save_geopolitics_events_for_round(
        self,
        scenario_id: str,
        result_id: str,
        round_result: dict[str, Any],
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        pool = get_pool()
        async with pool.acquire() as conn:
            for event_dict in round_result.get("events", []) + round_result.get("cascade_events", []):
                event_id = f"ge_{uuid.uuid4().hex[:12]}"
                await conn.execute(
                    """INSERT INTO geopolitics_events
                       (id, scenario_id, simulation_result_id, action_type, actor_id,
                        target_actor_ids, content, magnitude, round_number, event_at)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)""",
                    event_id,
                    scenario_id,
                    result_id,
                    event_dict.get("event_type", ""),
                    event_dict.get("source_actor_id", ""),
                    json.dumps(event_dict.get("target_actor_ids", [])),
                    event_dict.get("description", ""),
                    event_dict.get("magnitude", 0.5),
                    event_dict.get("round_number", 0),
                    now,
                )

    async def _save_wargame_state(
        self,
        scenario_id: str,
        result_id: str,
        current_round: int,
        total_rounds: int,
        engine: DecisionEngine | None,
        process_pid: int | None,
        status: str,
        last_heartbeat: str | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        heartbeat = last_heartbeat or now
        pool = get_pool()
        async with pool.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT id, engine_state FROM wargame_state WHERE result_id = $1 ORDER BY created_at DESC LIMIT 1",
                result_id,
            )
            if engine is not None:
                engine_state_json = json.dumps(engine.serialize_state(), ensure_ascii=False)
            elif existing and existing.get("engine_state"):
                engine_state_json = str(existing["engine_state"])
            else:
                engine_state_json = json.dumps({}, ensure_ascii=False)

            if existing:
                await conn.execute(
                    """UPDATE wargame_state
                       SET current_round = $1, total_rounds = $2, engine_state = $3,
                           process_pid = $4, status = $5, last_heartbeat = $6, updated_at = $7
                       WHERE id = $8""",
                    current_round,
                    total_rounds,
                    engine_state_json,
                    process_pid,
                    status,
                    heartbeat,
                    now,
                    existing["id"],
                )
            else:
                state_id = f"wg_{uuid.uuid4().hex[:12]}"
                await conn.execute(
                    """INSERT INTO wargame_state
                       (id, scenario_id, result_id, current_round, total_rounds, engine_state,
                        process_pid, status, last_heartbeat, created_at, updated_at)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)""",
                    state_id,
                    scenario_id,
                    result_id,
                    current_round,
                    total_rounds,
                    engine_state_json,
                    process_pid,
                    status,
                    heartbeat,
                    now,
                    now,
                )

    def _apply_simulation_actions_to_engine(
        self,
        engine: DecisionEngine,
        round_actions: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        mapped_actions = map_actions_to_geopolitics(round_actions)
        actor_ids = {a.actor_id for a in engine.get_all_actors()}
        applied_events: list[dict[str, Any]] = []
        for action in mapped_actions:
            source_actor = action.get("agent_name", "")
            if source_actor not in actor_ids:
                continue
            raw_type = (action.get("geopolitics_action") or action.get("action_type") or "").lower()
            event_type = GEOPOLITICS_ACTION_MAP.get(raw_type, raw_type)
            if not event_type:
                continue
            targets = [aid for aid in actor_ids if aid != source_actor][:2]
            if not targets:
                continue
            magnitude = 0.55 if event_type == "diplomatic_statement" else 0.35
            event = GeopoliticsEvent(
                event_type=event_type,
                source_actor_id=source_actor,
                target_actor_ids=targets,
                magnitude=magnitude,
                description=f"{source_actor}: {event_type}",
            )
            engine.apply_event(event)
            applied_events.append(event.to_dict())
        return applied_events

    @staticmethod
    def _compute_tension(actor_states: dict[str, Any]) -> float:
        if not actor_states:
            return 0.0
        values = [float(s.get("threat_perception", 0.0)) for s in actor_states.values() if isinstance(s, dict)]
        return round(sum(values) / len(values), 4) if values else 0.0

    @staticmethod
    def _severity_from_magnitude(magnitude: float) -> str:
        if magnitude >= 0.8:
            return "critical"
        if magnitude >= 0.6:
            return "high"
        if magnitude >= 0.3:
            return "medium"
        return "low"

    def _build_round_briefing(
        self,
        round_num: int,
        round_result: dict[str, Any],
        round_actions: list[dict[str, Any]],
        previous_decision_outcome: str | None = None,
    ) -> dict[str, Any]:
        events = list(round_result.get("events", [])) + list(round_result.get("cascade_events", []))
        key_events: list[dict[str, Any]] = []
        for event in events[:5]:
            event_type = str(event.get("event_type", "event"))
            magnitude = float(event.get("magnitude", 0.0))
            key_events.append(
                {
                    "type": event_type,
                    "description": str(event.get("description", ""))[:300],
                    "severity": self._severity_from_magnitude(magnitude),
                },
            )

        if not key_events:
            key_events.append(
                {
                    "type": "situation_update",
                    "description": f"라운드 {round_num} 완료. 지정학 이벤트는 감지되지 않았습니다.",
                    "severity": "low",
                },
            )

        actor_states = round_result.get("actor_states", {}) if isinstance(round_result.get("actor_states"), dict) else {}
        avg_threat = self._compute_tension(actor_states)
        avg_pressure = 0.0
        avg_resource = 0.0
        if actor_states:
            avg_pressure = round(
                sum(float(v.get("domestic_pressure", 0.0)) for v in actor_states.values() if isinstance(v, dict))
                / len(actor_states),
                4,
            )
            avg_resource = round(
                sum(float(v.get("resource_level", 0.0)) for v in actor_states.values() if isinstance(v, dict))
                / len(actor_states),
                4,
            )

        top_topics: list[str] = []
        for action in round_actions:
            action_type = str(action.get("geopolitics_action") or action.get("action_type") or "").strip()
            if action_type:
                top_topics.append(action_type)
        if not top_topics:
            top_topics = [str(e.get("event_type", "situation_update")) for e in events[:4] if isinstance(e, dict)]
        if not top_topics:
            top_topics = ["situation_update"]

        unique_topics: list[str] = []
        for topic in top_topics:
            if topic not in unique_topics:
                unique_topics.append(topic)

        return {
            "round": round_num,
            "key_events": key_events,
            "state_deltas": {
                "tension": avg_threat,
                "domestic_pressure": avg_pressure,
                "resource_level": avg_resource,
            },
            "previous_decision_outcome": previous_decision_outcome,
            "social_media_summary": {
                "total_posts": len(round_actions),
                "top_topics": unique_topics[:4],
            },
        }

    @staticmethod
    def _serialize_decision_point(
        dp_id: str,
        scenario_id: str,
        dp_type: str,
        options: list[dict[str, Any]],
        recommended: str,
    ) -> dict[str, Any]:
        return {
            "id": dp_id,
            "scenario_id": scenario_id,
            "type": dp_type,
            "options": options,
            "recommended": recommended,
            "allow_custom": True,
            "status": "pending",
            "selected_option_id": None,
            "custom_data": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "resolved_at": None,
        }

    async def _get_wargame_final_state(self, result_id: str) -> dict[str, Any]:
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT current_round, total_rounds, engine_state FROM wargame_state WHERE result_id = $1 ORDER BY updated_at DESC LIMIT 1",
                result_id,
            )
        if not row:
            return {"round": 0, "total_rounds": 0, "tension": 0.0, "actor_states": {}}

        engine_state = json.loads(row["engine_state"]) if row["engine_state"] else {}
        actor_states = engine_state.get("actors", {}) if isinstance(engine_state.get("actors"), dict) else {}
        return {
            "round": int(row["current_round"] or 0),
            "total_rounds": int(row["total_rounds"] or 0),
            "tension": float(engine_state.get("global_tension", self._compute_tension(actor_states))),
            "actor_states": actor_states,
        }

    async def _cancel_heartbeat_task(self, result_id: str) -> None:
        task = self._wargame_heartbeat_tasks.pop(result_id, None)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def _is_latest_decision_resolved(self, scenario_id: str, result_id: str) -> bool:
        snapshot = await get_latest_snapshot(scenario_id, result_id)
        if not snapshot:
            return False
        pending_dp_id = snapshot.get("pending_decision_point_id")
        if not pending_dp_id:
            return False
        pool = get_pool()
        async with pool.acquire() as conn:
            status = await conn.fetchval("SELECT status FROM decision_points WHERE id = $1", pending_dp_id)
        return status == "resolved"

    async def _auto_complete_latest_decision(
        self,
        scenario_id: str,
        result_id: str,
    ) -> str | None:
        snapshot = await get_latest_snapshot(scenario_id, result_id)
        if not snapshot:
            return None

        pending_dp_id = snapshot.get("pending_decision_point_id")
        if not pending_dp_id:
            return None

        pool = get_pool()
        async with pool.acquire() as conn:
            dp_row = await conn.fetchrow(
                "SELECT id, status, recommended, options, selected_option_id FROM decision_points WHERE id = $1",
                pending_dp_id,
            )
            if not dp_row:
                return None

            selected_option_id = dp_row["selected_option_id"] or dp_row["recommended"]
            if dp_row["status"] != "resolved":
                selected_option_id = dp_row["recommended"]
                if not selected_option_id:
                    options = json.loads(dp_row["options"]) if dp_row["options"] else []
                    if options:
                        selected_option_id = options[0].get("id")
                if not selected_option_id:
                    return None

                now = datetime.now(timezone.utc).isoformat()
                auto_custom_data = json.dumps(
                    {
                        "auto_completed": True,
                        "reason": "idle_ttl_expired",
                        "resolved_by": "system",
                    },
                    ensure_ascii=False,
                )
                update_result = await conn.execute(
                    """UPDATE decision_points
                       SET status = 'resolved', selected_option_id = $1, custom_data = $2, resolved_at = $3
                       WHERE id = $4 AND status = 'pending'""",
                    selected_option_id,
                    auto_custom_data,
                    now,
                    pending_dp_id,
                )
                if not str(update_result).endswith("1"):
                    status = await conn.fetchval(
                        "SELECT status FROM decision_points WHERE id = $1",
                        pending_dp_id,
                    )
                    if status != "resolved":
                        return None

        outcome = f"입력 대기 TTL 만료로 권장 결정안({selected_option_id})이 자동 반영되었습니다."
        await ActionLogger.log(
            "wargame.decision_auto_completed",
            scenario_id,
            payload={
                "result_id": result_id,
                "decision_point_id": pending_dp_id,
                "selected_option_id": selected_option_id,
                "reason": "idle_ttl_expired",
            },
        )
        await self._emit_sse(
            scenario_id,
            "decision_auto_completed",
            {
                "decision_point_id": pending_dp_id,
                "selected": selected_option_id,
                "outcome": outcome,
                "reason": "idle_ttl_expired",
                "round": int(snapshot.get("round_number") or 0),
            },
        )
        return outcome

    async def _finalize_wargame(
        self,
        scenario_id: str,
        result_id: str,
        mf_simulation_id: str,
        simulation_params: SimulationParams,
        total_rounds: int,
    ) -> None:
        await self._cancel_heartbeat_task(result_id)
        await self._step_report(scenario_id, result_id, mf_simulation_id)
        await self._collect_and_store_results(result_id, mf_simulation_id, simulation_params=simulation_params)
        await self._save_wargame_state(
            scenario_id,
            result_id,
            current_round=total_rounds,
            total_rounds=total_rounds,
            engine=None,
            process_pid=None,
            status="completed",
        )
        final_state = await self._get_wargame_final_state(result_id)
        await self._emit_sse(
            scenario_id,
            "phase_change",
            {"phase": "confirmation", "round": total_rounds},
        )
        await self._emit_sse(
            scenario_id,
            "simulation_complete",
            {
                "result_id": result_id,
                "total_rounds": total_rounds,
                "final_state": final_state,
            },
        )

    async def _start_heartbeat_loop(
        self,
        scenario_id: str,
        result_id: str,
        mf_simulation_id: str,
        simulation_params: SimulationParams,
        total_rounds: int,
        current_round: int,
    ) -> None:
        ttl_minutes = simulation_params.wargame_idle_ttl_minutes
        deadline = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)
        while datetime.now(timezone.utc) < deadline:
            await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
            if await self._is_latest_decision_resolved(scenario_id, result_id):
                return

            ts = datetime.now(timezone.utc).isoformat()
            try:
                await self._send_control_signal(
                    mf_simulation_id,
                    {"type": "heartbeat", "timestamp": ts},
                )
                run_status = await self.mf.get_run_status(mf_simulation_id)
            except Exception:
                await self._save_wargame_state(
                    scenario_id,
                    result_id,
                    current_round=current_round,
                    total_rounds=total_rounds,
                    engine=None,
                    process_pid=None,
                    status="crashed",
                )
                await self._emit_sse(
                    scenario_id,
                    "phase_change",
                    {"phase": "briefing", "round": current_round, "status": "crashed"},
                )
                return
            runner_status = str(run_status.get("runner_status", "")).lower()
            if runner_status in {"failed", "stopped"}:
                await self._save_wargame_state(
                    scenario_id,
                    result_id,
                    current_round=current_round,
                    total_rounds=total_rounds,
                    engine=None,
                    process_pid=None,
                    status="crashed",
                )
                await self._emit_sse(
                    scenario_id,
                    "phase_change",
                    {"phase": "briefing", "round": current_round, "status": "crashed"},
                )
                return

            ttl_remaining = max(0, int((deadline - datetime.now(timezone.utc)).total_seconds()))
            await self._emit_sse(
                scenario_id,
                "heartbeat",
                {
                    "timestamp": ts,
                    "round": current_round,
                    "ttl_seconds_remaining": ttl_remaining,
                },
            )
            await self._save_wargame_state(
                scenario_id,
                result_id,
                current_round=current_round,
                total_rounds=total_rounds,
                engine=None,
                process_pid=None,
                status="paused",
                last_heartbeat=ts,
            )

        snapshot = await get_latest_snapshot(scenario_id, result_id)
        pending_dp_id = snapshot.get("pending_decision_point_id") if snapshot else None
        auto_outcome = await self._auto_complete_latest_decision(scenario_id, result_id)
        if not auto_outcome:
            await self._save_wargame_state(
                scenario_id,
                result_id,
                current_round=current_round,
                total_rounds=total_rounds,
                engine=None,
                process_pid=None,
                status="paused",
            )
            await self._emit_sse(
                scenario_id,
                "phase_change",
                {"phase": "briefing", "round": current_round, "status": "idle_timeout_no_pending_decision"},
            )
            return

        await self._emit_sse(
            scenario_id,
            "phase_change",
            {
                "phase": "simulation",
                "round": current_round + 1,
                "status": "idle_timeout_auto_continue",
            },
        )
        try:
            await self._continue_wargame(
                scenario_id,
                result_id,
                simulation_params,
                previous_decision_outcome=auto_outcome,
                skip_cancel_heartbeat=True,
                expected_decision_point_id=pending_dp_id,
            )
        except Exception:
            logger.exception("[%s] TTL auto-continue failed", scenario_id)
            await self._update_status(scenario_id, result_id, "failed")

    async def _run_wargame_round_loop(
        self,
        scenario_id: str,
        result_id: str,
        mf_simulation_id: str,
        start_round: int,
        total_rounds: int,
        simulation_params: SimulationParams,
        engine: DecisionEngine | None,
        inject_context: dict[str, Any] | None,
        previous_decision_outcome: str | None = None,
    ) -> tuple[str, int]:
        current_inject = inject_context
        cumulative_actions: list[dict[str, Any]] = []
        for round_num in range(start_round, total_rounds + 1):
            payload = {"type": "proceed", "round": round_num}
            if current_inject:
                payload["inject_context"] = current_inject
            signal = await self._send_control_signal(mf_simulation_id, payload)
            signal_type = signal.get("type")
            if signal_type == "error":
                raise RuntimeError(signal.get("message", "wargame round error"))
            if signal_type != "round_complete":
                continue
            signal_round = signal.get("round")
            if signal_round is not None and int(signal_round) != round_num:
                raise RuntimeError(
                    f"round mismatch: expected {round_num}, got {signal_round}"
                )

            round_actions = signal.get("actions", [])
            if not isinstance(round_actions, list):
                round_actions = []
            await self._save_round_actions(scenario_id, round_num, round_actions)
            cumulative_actions.extend(round_actions)

            if engine is None:
                engine = self._init_geopolitics_engine(cumulative_actions)
            elif len(engine.get_all_actors()) < 2:
                rebuilt_engine = self._init_geopolitics_engine(cumulative_actions)
                if rebuilt_engine is not None and len(rebuilt_engine.get_all_actors()) >= 2:
                    engine = rebuilt_engine
            round_result: dict[str, Any] = {"round": round_num, "events": [], "cascade_events": [], "actor_states": {}}
            if engine is not None:
                applied_events = self._apply_simulation_actions_to_engine(engine, round_actions)
                round_result = engine.run_single_round()
                round_result["events"] = applied_events + list(round_result.get("events", []))
                await self._save_geopolitics_events_for_round(scenario_id, result_id, round_result)

            stats = signal.get("stats", {}) if isinstance(signal.get("stats"), dict) else {}
            geo_event_count = len(round_result.get("events", [])) + len(round_result.get("cascade_events", []))
            actor_states = round_result.get("actor_states", {}) if isinstance(round_result.get("actor_states"), dict) else {}
            await self._save_wargame_state(
                scenario_id,
                result_id,
                current_round=round_num,
                total_rounds=total_rounds,
                engine=engine,
                process_pid=None,
                status="running",
            )
            await self._emit_sse(
                scenario_id,
                "round_complete",
                {
                    "round": round_num,
                    "actions_count": len(round_actions),
                    "geo_events": geo_event_count,
                    "stats": stats,
                    "tension": self._compute_tension(actor_states),
                    "actor_states": actor_states,
                },
            )
            await self._emit_sse(
                scenario_id,
                "round_stats",
                {
                    "round": round_num,
                    "tension": self._compute_tension(actor_states),
                    "actor_states": actor_states,
                },
            )

            # Wargame round loop은 항상 주기적으로 멈춰야 브리핑을 보여줄 수 있다.
            # AUTO 모드일 때 should_pause가 항상 False를 반환하므로,
            # 워게임 컨텍스트에서는 GAME_MASTER로 오버라이드한다.
            effective_mode = simulation_params.geopolitics_mode
            if effective_mode == GeopoliticsMode.AUTO:
                effective_mode = GeopoliticsMode.GAME_MASTER

            if engine is not None:
                should_pause_now = should_pause(
                    round_result,
                    effective_mode,
                    simulation_params.geopolitics_player_actor_id,
                    simulation_params.geopolitics_pause_threshold,
                    pause_interval=simulation_params.geopolitics_rounds,
                )
            else:
                # 엔진 없음 — 이벤트 기반 판단 불가, 주기 기반으로 일시정지
                _pi = simulation_params.geopolitics_rounds
                should_pause_now = round_num >= 2 and (
                    round_num == 2 or (_pi > 0 and (round_num - 2) % _pi == 0)
                )

            if should_pause_now:
                pause_engine = engine if engine is not None else DecisionEngine()
                snapshot_id = await save_geopolitics_snapshot(
                    scenario_id,
                    result_id,
                    round_num,
                    pause_engine,
                    effective_mode,
                    simulation_params.geopolitics_player_actor_id,
                )
                if engine is not None and effective_mode == GeopoliticsMode.ACTOR_ROLE and simulation_params.geopolitics_player_actor_id:
                    trigger_event = find_trigger_event(round_result, simulation_params.geopolitics_player_actor_id)
                    options = build_actor_response_options(engine, simulation_params.geopolitics_player_actor_id, trigger_event or {})
                    dp_type = "geopolitics_actor_response"
                    if options:
                        recommended = next((o["id"] for o in options if o.get("data", {}).get("engine_recommended")), options[0]["id"])
                    else:
                        options = build_direction_options(round_result)
                        dp_type = "geopolitics_direction"
                        recommended = "maintain"
                else:
                    options = build_direction_options(round_result)
                    dp_type = "geopolitics_direction"
                    recommended = "maintain"

                dp_id = await create_geopolitics_decision_point(scenario_id, dp_type, options, recommended)
                await link_snapshot_to_dp(snapshot_id, dp_id)
                briefing = self._build_round_briefing(
                    round_num,
                    round_result,
                    round_actions,
                    previous_decision_outcome=previous_decision_outcome,
                )
                await ActionLogger.log(
                    "wargame.round_briefing",
                    scenario_id,
                    payload={
                        "result_id": result_id,
                        "round": round_num,
                        "decision_point_id": dp_id,
                        "briefing": briefing,
                    },
                )
                decision_point_payload = self._serialize_decision_point(
                    dp_id=dp_id,
                    scenario_id=scenario_id,
                    dp_type=dp_type,
                    options=options,
                    recommended=recommended,
                )
                await self._update_status(scenario_id, result_id, f"wargame:paused:round_{round_num}")
                await self._save_wargame_state(
                    scenario_id,
                    result_id,
                    current_round=round_num,
                    total_rounds=total_rounds,
                    engine=pause_engine,
                    process_pid=None,
                    status="paused",
                )
                await self._emit_sse(
                    scenario_id,
                    "phase_change",
                    {"phase": "briefing", "round": round_num},
                )
                await self._emit_sse(
                    scenario_id,
                    "decision_required",
                    {
                        "round": round_num,
                        "decision_point_id": dp_id,
                        "briefing": briefing,
                        "decision_point": decision_point_payload,
                    },
                )
                await self._cancel_heartbeat_task(result_id)
                heartbeat_task = asyncio.create_task(
                    self._start_heartbeat_loop(
                        scenario_id,
                        result_id,
                        mf_simulation_id,
                        simulation_params,
                        total_rounds,
                        round_num,
                    )
                )
                self._wargame_heartbeat_tasks[result_id] = heartbeat_task
                return "paused", round_num

            current_inject = build_inject_context(engine, round_result) if engine else None

        return "completed", total_rounds

    async def run_wargame_pipeline(
        self,
        scenario_id: str,
        result_id: str,
        seed_text: str,
        max_rounds: int,
        simulation_params: SimulationParams,
    ) -> None:
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
                except Exception:
                    logger.warning("[%s] Snapshot creation failed, continuing", scenario_id)

            await self._emit_sse(scenario_id, "phase_change", {"phase": "simulation", "round": 0})
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

            try:
                await self.mf.stop_simulation(mf_simulation_id)
            except Exception:
                pass
            await asyncio.sleep(3)

            ready_signal = await self._start_wargame_process(
                mf_simulation_id,
                max_rounds,
                simulation_params,
            )
            ready_signal = await self._read_control_signal(ready_signal)
            if ready_signal.get("type") != "ready":
                raise RuntimeError(f"unexpected control signal: {ready_signal}")

            await self._update_status(scenario_id, result_id, "simulating:wargame")
            await self._save_wargame_state(
                scenario_id,
                result_id,
                current_round=0,
                total_rounds=max_rounds,
                engine=None,
                process_pid=None,
                status="running",
            )

            loop_status, _ = await self._run_wargame_round_loop(
                scenario_id,
                result_id,
                mf_simulation_id,
                start_round=1,
                total_rounds=max_rounds,
                simulation_params=simulation_params,
                engine=None,
                inject_context=None,
            )
            if loop_status == "paused":
                return

            await self._send_control_signal(
                mf_simulation_id,
                {"type": "stop", "reason": "completed"},
            )
            await self._finalize_wargame(
                scenario_id,
                result_id,
                mf_simulation_id,
                simulation_params,
                max_rounds,
            )
        except Exception as exc:
            logger.exception("[%s] Wargame pipeline failed", scenario_id)
            await self._update_status(scenario_id, result_id, "failed")
            await ActionLogger.log(
                "pipeline.wargame_failed",
                scenario_id,
                payload={"error": str(exc)[:500]},
            )

    async def _continue_wargame(
        self,
        scenario_id: str,
        result_id: str,
        simulation_params: SimulationParams,
        previous_decision_outcome: str | None = None,
        skip_cancel_heartbeat: bool = False,
        expected_decision_point_id: str | None = None,
    ) -> None:
        async with self._get_wargame_continue_lock(result_id):
            pool = get_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT mirofish_simulation_id FROM simulation_results WHERE id = $1",
                    result_id,
                )
            if not row or not row["mirofish_simulation_id"]:
                raise RuntimeError("MiroFish simulation id not found for wargame resume")
            mf_simulation_id = row["mirofish_simulation_id"]

            if not skip_cancel_heartbeat:
                await self._cancel_heartbeat_task(result_id)

            snapshot = None
            if expected_decision_point_id:
                snapshot = await self._consume_pending_snapshot_decision(
                    scenario_id,
                    result_id,
                    expected_decision_point_id,
                )
                if snapshot is None:
                    logger.info(
                        "[%s] Skipping duplicate wargame continue for consumed decision %s",
                        scenario_id,
                        expected_decision_point_id,
                    )
                    return
            else:
                snapshot = await get_latest_snapshot(scenario_id, result_id)
                if not snapshot:
                    raise RuntimeError("No geopolitics snapshot found")

            run_status = await self.mf.get_run_status(mf_simulation_id)
            runner_status = str(run_status.get("runner_status", "")).lower()

            async with pool.acquire() as conn:
                wargame_row_early = await conn.fetchrow(
                    "SELECT total_rounds FROM wargame_state WHERE result_id = $1 ORDER BY updated_at DESC LIMIT 1",
                    result_id,
                )
            total_rounds_for_restart = (
                int(wargame_row_early["total_rounds"])
                if wargame_row_early
                else int(run_status.get("total_rounds") or (int(snapshot["round_number"]) + 1))
            )

            if runner_status not in {"running", "paused"}:
                ready_signal = await self._start_wargame_process(
                    mf_simulation_id,
                    total_rounds_for_restart,
                    simulation_params,
                )
                ready_signal = await self._read_control_signal(ready_signal)
                if ready_signal.get("type") != "ready":
                    raise RuntimeError("Failed to restart round-controlled wargame process")
                await ActionLogger.log(
                    "wargame.recovered",
                    scenario_id,
                    payload={"result_id": result_id, "recovered_from": runner_status},
                )
                await self._emit_sse(
                    scenario_id,
                    "phase_change",
                    {
                        "phase": "simulation",
                        "round": int(snapshot["round_number"]) + 1,
                        "recovered": True,
                    },
                )

            pending_dp_id = expected_decision_point_id or snapshot.get("pending_decision_point_id")
            async with pool.acquire() as conn:
                wargame_row = await conn.fetchrow(
                    "SELECT total_rounds FROM wargame_state WHERE result_id = $1 ORDER BY updated_at DESC LIMIT 1",
                    result_id,
                )
                dp_row = await conn.fetchrow(
                    "SELECT type, options, selected_option_id, custom_data FROM decision_points WHERE id = $1 AND status = 'resolved'",
                    pending_dp_id,
                )
            if not dp_row:
                logger.info(
                    "[%s] Skipping wargame continue because decision %s is not resolved",
                    scenario_id,
                    pending_dp_id,
                )
                return

            engine_state = json.loads(snapshot["engine_state"]) if snapshot.get("engine_state") else {}
            engine = DecisionEngine.from_state(engine_state)
            mode = GeopoliticsMode(snapshot["geopolitics_mode"])

            selected_option = dp_row["selected_option_id"]
            user_decision: dict[str, Any] | None = None
            decision_label = selected_option or "maintain"
            decision_outcome = "결정이 반영되어 다음 라운드에 적용됩니다."
            if mode == GeopoliticsMode.ACTOR_ROLE and snapshot.get("player_actor_id") and selected_option:
                actor_id = snapshot["player_actor_id"]
                engine.override_next_action(actor_id, selected_option)
                actor = engine.get_actor(actor_id)
                user_decision = {
                    "action": selected_option,
                    "actor_id": actor_id,
                    "actor_name": actor.name if actor else actor_id,
                }
                decision_label = selected_option
                decision_outcome = f"{user_decision['actor_name']} 행동이 다음 라운드 우선 행동으로 고정됩니다."
            elif mode == GeopoliticsMode.GAME_MASTER:
                options = json.loads(dp_row["options"]) if dp_row["options"] else []
                selected = next((o for o in options if o["id"] == selected_option), None)
                if selected and selected.get("data"):
                    deltas = selected["data"].get("state_deltas", {})
                    applies_to = selected["data"].get("applies_to", "all")
                    engine.apply_direction_deltas(deltas, applies_to)
                    user_decision = {"action": selected_option or "maintain", "actor_name": "GameMaster"}
                    decision_label = selected.get("label", selected_option or "maintain")
                    decision_outcome = selected.get("description", decision_outcome)

            inject_context = build_inject_context(
                engine,
                {
                    "round": snapshot["round_number"],
                    "events": [],
                    "cascade_events": [],
                },
                user_decision=user_decision,
            )

            if not previous_decision_outcome:
                previous_decision_outcome = decision_outcome

            await self._emit_sse(
                scenario_id,
                "decision_resolved",
                {
                    "decision_point_id": pending_dp_id,
                    "selected": selected_option,
                    "label": decision_label,
                    "outcome": previous_decision_outcome,
                    "round": int(snapshot["round_number"]),
                },
            )
            await self._emit_sse(
                scenario_id,
                "phase_change",
                {"phase": "simulation", "round": snapshot["round_number"] + 1},
            )
            await self._update_status(scenario_id, result_id, "simulating:wargame")

            total_rounds = int(wargame_row["total_rounds"]) if wargame_row else int(snapshot["round_number"])
            loop_status, _ = await self._run_wargame_round_loop(
                scenario_id,
                result_id,
                mf_simulation_id,
                start_round=int(snapshot["round_number"]) + 1,
                total_rounds=total_rounds,
                simulation_params=simulation_params,
                engine=engine,
                inject_context=inject_context,
                previous_decision_outcome=previous_decision_outcome,
            )
            if loop_status == "paused":
                return

            await self._send_control_signal(
                mf_simulation_id,
                {"type": "stop", "reason": "completed"},
            )
            await self._finalize_wargame(
                scenario_id,
                result_id,
                mf_simulation_id,
                simulation_params,
                total_rounds,
            )

    async def continue_wargame(
        self,
        scenario_id: str,
        result_id: str,
        simulation_params: SimulationParams,
        expected_decision_point_id: str | None = None,
    ) -> None:
        await self._continue_wargame(
            scenario_id,
            result_id,
            simulation_params,
            expected_decision_point_id=expected_decision_point_id,
        )

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
