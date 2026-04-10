from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

import asyncpg
from langgraph.types import Command

from app.config import settings
from app.graph.builder import get_graph

logger = logging.getLogger(__name__)

_CHANNEL = "sim_commands"

class SimulationCommandListener:
    def __init__(self) -> None:
        self._graph = None
        self._running_tasks: dict[str, asyncio.Task] = {}
        self._scenario_modes: dict[str, str] = {}

    def set_graph(self, graph: Any) -> None:
        self._graph = graph

    async def _graph_for_mode(self, mode: str) -> Any:
        return await get_graph(mode)

    async def _graph_for_scenario(self, scenario_id: str) -> Any:
        mode = self._scenario_modes.get(scenario_id, "auto")
        return await get_graph(mode)

    async def _check_interrupt(self, graph: Any, config: dict) -> Any | None:
        snapshot = await graph.aget_state(config)
        if snapshot and snapshot.tasks:
            for task in snapshot.tasks:
                if hasattr(task, "interrupts") and task.interrupts:
                    return task.interrupts[0].value
        return None

    async def start(self) -> None:
        delay = 1.0
        while True:
            try:
                conn = await asyncpg.connect(settings.database_url)
                delay = 1.0
                queue: asyncio.Queue[str] = asyncio.Queue()

                def _on_notification(
                    _conn: asyncpg.Connection,
                    _pid: int,
                    _channel: str,
                    payload: str,
                ) -> None:
                    queue.put_nowait(payload)

                await conn.add_listener(_CHANNEL, _on_notification)
                logger.info("LISTEN %s started", _CHANNEL)

                try:
                    while True:
                        raw = await queue.get()
                        try:
                            command = json.loads(raw)
                            await self._handle_command(command)
                        except json.JSONDecodeError:
                            logger.warning("Invalid JSON on %s: %s", _CHANNEL, raw[:200])
                        except Exception:
                            logger.exception("Command handler error")
                finally:
                    await conn.remove_listener(_CHANNEL, _on_notification)
                    await conn.close()

            except asyncio.CancelledError:
                logger.info("LISTEN %s cancelled", _CHANNEL)
                raise
            except Exception:
                logger.exception("LISTEN %s connection lost, reconnecting in %.1fs", _CHANNEL, delay)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30.0)

    async def _handle_command(self, command: dict[str, Any]) -> None:
        cmd_type = command.get("type")
        scenario_id = command.get("scenario_id", "")

        if cmd_type == "start_simulation":
            await self._start_simulation(scenario_id, command)
        elif cmd_type == "stop_simulation":
            await self._stop_simulation(scenario_id)
        elif cmd_type == "user_decision":
            await self._apply_decision(scenario_id, command)
        elif cmd_type == "resume_simulation":
            await self._resume_simulation(scenario_id)
        elif cmd_type == "start_whatif":
            await self._start_whatif(scenario_id, command)
        else:
            logger.warning("Unknown command type: %s", cmd_type)

    async def _start_simulation(self, scenario_id: str, command: dict) -> None:
        if scenario_id in self._running_tasks:
            logger.warning("Simulation %s already running", scenario_id)
            return

        mode = command.get("mode", "auto")
        if mode not in ("auto", "checkpoint"):
            mode = "auto"
        self._scenario_modes[scenario_id] = mode
        graph = await self._graph_for_mode(mode)

        from app.services.event_emitter import get_emitter

        emitter = get_emitter()

        async def _run() -> None:
            try:
                config = {"configurable": {"thread_id": scenario_id}}
                initial_state = {
                    "scenario_id": scenario_id,
                    "pipeline_mode": mode,
                    "seed_text": command.get("seed_text", ""),
                    "region_bbox": command.get("region_bbox", []),
                    "region_name": command.get("region_name", ""),
                    "question": command.get("question", ""),
                    "ontology_version": "v12.0",
                    "graph_id": "",
                    "situation_summary": "",
                    "actors": {},
                    "actor_states": {},
                    "current_round": 0,
                    "max_rounds": command.get("max_rounds", 10),
                    "round_actions": [],
                    "action_history": [],
                    "tension_levels": {},
                    "decision_engine_state": {},
                    "decision_point": None,
                    "user_decision": None,
                    "graph_entities": [],
                    "graph_relations": [],
                    "completed_checkpoints": [],
                    "round_events": [],
                    "round_cascades": [],
                    "hit_trigger": None,
                    "phase": "analyzing",
                    "status": "running",
                    "messages": [],
                }

                await emitter.emit_phase_change(scenario_id, "analyzing", 0)

                result = await graph.ainvoke(initial_state, config)

                interrupt_value = await self._check_interrupt(graph, config)
                if interrupt_value is not None:
                    if isinstance(interrupt_value, dict) and interrupt_value.get("type") == "pipeline_checkpoint":
                        await emitter.emit_checkpoint_reached(
                            scenario_id,
                            interrupt_value.get("step", "unknown"),
                            interrupt_value.get("state", {}),
                        )
                        await self._update_scenario_status(scenario_id, "paused")
                        return
                    await self._persist_intervention_decision_point(scenario_id, interrupt_value)
                    await emitter.emit_intervention_required(scenario_id, interrupt_value)
                    await self._update_scenario_status(scenario_id, "paused")
                    return

                if isinstance(result, dict) and result.get("status") == "completed":
                    await self._update_scenario_status(scenario_id, "completed")

            except asyncio.CancelledError:
                await emitter.emit_phase_change(scenario_id, "cancelled", 0)
                await self._update_scenario_status(scenario_id, "cancelled")
            except Exception as exc:
                logger.exception("Simulation %s failed", scenario_id)
                await emitter.emit_error(scenario_id, str(exc))
                await self._update_scenario_status(scenario_id, "failed")
            finally:
                self._running_tasks.pop(scenario_id, None)

        task = asyncio.create_task(_run())
        self._running_tasks[scenario_id] = task

    async def _update_scenario_status(self, scenario_id: str, status: str) -> None:
        try:
            import asyncpg
            from app.config import settings
            conn = await asyncpg.connect(settings.database_url)
            await conn.execute(
                "UPDATE scenarios SET simulation_status = $1 WHERE id = $2",
                status, scenario_id,
            )
            if status == "completed":
                await conn.execute(
                    "UPDATE scenarios SET status = 'completed' WHERE id = $1",
                    scenario_id,
                )
            await conn.close()
        except Exception:
            logger.warning("Failed to update scenario %s status to %s", scenario_id, status)

    async def _stop_simulation(self, scenario_id: str) -> None:
        task = self._running_tasks.pop(scenario_id, None)
        if task and not task.done():
            task.cancel()
            logger.info("Simulation %s cancelled", scenario_id)

    async def _apply_decision(self, scenario_id: str, command: dict) -> None:
        graph = await self._graph_for_scenario(scenario_id)
        config = {"configurable": {"thread_id": scenario_id}}
        await self._resolve_intervention_decision_point(scenario_id, command.get("chosen_action", {}))
        result = await graph.ainvoke(Command(resume=command.get("chosen_action")), config)

        from app.services.event_emitter import get_emitter
        emitter = get_emitter()

        interrupt_value = await self._check_interrupt(graph, config)
        if interrupt_value is not None:
            if isinstance(interrupt_value, dict) and interrupt_value.get("type") == "pipeline_checkpoint":
                await emitter.emit_checkpoint_reached(
                    scenario_id,
                    interrupt_value.get("step", "unknown"),
                    interrupt_value.get("state", {}),
                )
                await self._update_scenario_status(scenario_id, "paused")
                return
            await self._persist_intervention_decision_point(scenario_id, interrupt_value)
            await emitter.emit_intervention_required(scenario_id, interrupt_value)
            await self._update_scenario_status(scenario_id, "paused")
            return

        await self._update_scenario_status(scenario_id, "running")
        if isinstance(result, dict) and result.get("status") == "completed":
            await self._update_scenario_status(scenario_id, "completed")

    async def _resume_simulation(self, scenario_id: str) -> None:
        graph = await self._graph_for_scenario(scenario_id)
        config = {"configurable": {"thread_id": scenario_id}}
        result = await graph.ainvoke(Command(resume={"continue": True}), config)

        from app.services.event_emitter import get_emitter
        emitter = get_emitter()

        interrupt_value = await self._check_interrupt(graph, config)
        if interrupt_value is not None:
            if isinstance(interrupt_value, dict) and interrupt_value.get("type") == "pipeline_checkpoint":
                await emitter.emit_checkpoint_reached(
                    scenario_id,
                    interrupt_value.get("step", "unknown"),
                    interrupt_value.get("state", {}),
                )
                await self._update_scenario_status(scenario_id, "paused")
                return
            await self._persist_intervention_decision_point(scenario_id, interrupt_value)
            await emitter.emit_intervention_required(scenario_id, interrupt_value)
            await self._update_scenario_status(scenario_id, "paused")
            return

        await self._update_scenario_status(scenario_id, "running")
        if isinstance(result, dict) and result.get("status") == "completed":
            await self._update_scenario_status(scenario_id, "completed")
        logger.info("Simulation %s resumed", scenario_id)

    @staticmethod
    def _canonicalize_decision_options(decision_point: dict[str, Any]) -> list[dict[str, Any]]:
        options = decision_point.get("options", [])
        if not isinstance(options, list):
            return []

        canonical: list[dict[str, Any]] = []
        for index, option in enumerate(options):
            if not isinstance(option, dict):
                continue
            action_type = str(option.get("action_type", "action"))
            target = str(option.get("target", ""))
            description = str(option.get("description") or f"{target} {action_type}")
            canonical.append({
                "id": f"{action_type}-{target}-{index}",
                "label": description,
                "description": description,
                "confidence": 1.0,
                "reasoning": description,
                "data": option,
            })
        return canonical

    async def _persist_intervention_decision_point(self, scenario_id: str, decision_point: Any) -> None:
        if not isinstance(decision_point, dict):
            return

        dp_id = decision_point.get("id")
        if not isinstance(dp_id, str) or not dp_id:
            return

        options = self._canonicalize_decision_options(decision_point)
        if not options:
            return

        now = datetime.now(timezone.utc).isoformat()
        recommended = options[0]["id"]
        dp_type = decision_point.get("type", "geopolitics_actor_response")

        conn = await asyncpg.connect(settings.database_url)
        try:
            await conn.execute(
                """INSERT INTO decision_points
                   (id, scenario_id, type, options, recommended, allow_custom, status, selected_option_id, custom_data, created_at, resolved_at)
                   VALUES ($1, $2, $3, $4, $5, FALSE, 'pending', NULL, NULL, $6, NULL)
                   ON CONFLICT (id) DO NOTHING""",
                dp_id,
                scenario_id,
                dp_type,
                json.dumps(options, ensure_ascii=False),
                recommended,
                now,
            )
        finally:
            await conn.close()

    async def _resolve_intervention_decision_point(self, scenario_id: str, chosen_action: Any) -> None:
        if not isinstance(chosen_action, dict):
            return

        dp_id = chosen_action.get("decision_point_id")
        if not isinstance(dp_id, str) or not dp_id:
            return

        conn = await asyncpg.connect(settings.database_url)
        try:
            row = await conn.fetchrow(
                "SELECT options, status FROM decision_points WHERE id = $1 AND scenario_id = $2",
                dp_id,
                scenario_id,
            )
            if not row or row["status"] == "resolved":
                return

            selected_option_id = chosen_action.get("selected_option_id")
            options = json.loads(row["options"]) if isinstance(row["options"], str) else row["options"]
            if not isinstance(selected_option_id, str) or not selected_option_id:
                for option in options:
                    data = option.get("data", {}) if isinstance(option, dict) else {}
                    if not isinstance(data, dict):
                        continue
                    if (
                        data.get("action_type") == chosen_action.get("action_type")
                        and data.get("target") == chosen_action.get("target")
                        and data.get("intensity") == chosen_action.get("intensity")
                    ):
                        selected_option_id = option.get("id")
                        break

            now = datetime.now(timezone.utc).isoformat()
            custom_data = None if selected_option_id else json.dumps(chosen_action, ensure_ascii=False)
            await conn.execute(
                """UPDATE decision_points
                   SET status = 'resolved', selected_option_id = $1, custom_data = $2, resolved_at = $3
                   WHERE id = $4 AND scenario_id = $5""",
                selected_option_id,
                custom_data,
                now,
                dp_id,
                scenario_id,
            )
        finally:
            await conn.close()

    async def _start_whatif(self, scenario_id: str, command: dict) -> None:
        if self._graph is None:
            logger.error("Graph not initialized")
            return

        graph = self._graph
        branch_id = command.get("branch_id", "")
        branch_round = command.get("branch_point_round", 0)

        source_config = {"configurable": {"thread_id": scenario_id}}
        state_snapshot = await graph.aget_state(source_config)

        if not state_snapshot or not state_snapshot.values:
            logger.error("No state found for %s", scenario_id)
            return

        branch_state = dict(state_snapshot.values)
        branch_state["scenario_id"] = branch_id

        chosen = command.get("chosen_action")
        if chosen:
            branch_state["user_decision"] = chosen
            branch_state["decision_point"] = None

        if branch_round and branch_state.get("current_round", 0) > branch_round:
            branch_state["current_round"] = branch_round
            branch_state["action_history"] = [
                a for a in branch_state.get("action_history", [])
                if a.get("round", 999) <= branch_round
            ]

        from app.services.event_emitter import get_emitter
        emitter = get_emitter()

        branch_config = {"configurable": {"thread_id": branch_id}}

        async def _run_branch() -> None:
            try:
                await emitter.emit_phase_change(branch_id, "simulating", 0)
                result = await graph.ainvoke(branch_state, branch_config)

                import asyncpg
                from app.config import settings
                pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=1)
                async with pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE whatif_branches SET status = 'completed', completed_at = NOW() WHERE id = $1",
                        branch_id,
                    )
                await pool.close()

            except Exception as exc:
                logger.exception("What-if branch %s failed", branch_id)
                await emitter.emit_error(branch_id, str(exc))

        task = asyncio.create_task(_run_branch())
        self._running_tasks[branch_id] = task
