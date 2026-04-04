from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import asyncpg

from app.config import settings

logger = logging.getLogger(__name__)

_CHANNEL = "sim_commands"


class SimulationCommandListener:
    def __init__(self) -> None:
        self._graph = None
        self._running_tasks: dict[str, asyncio.Task] = {}

    def set_graph(self, graph: Any) -> None:
        self._graph = graph

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

        if self._graph is None:
            logger.error("Graph not initialized")
            return

        graph = self._graph
        from app.services.event_emitter import get_emitter

        emitter = get_emitter()

        async def _run() -> None:
            try:
                config = {"configurable": {"thread_id": scenario_id}}
                initial_state = {
                    "scenario_id": scenario_id,
                    "seed_text": command.get("seed_text", ""),
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
                    "phase": "analyzing",
                    "status": "running",
                }

                await emitter.emit_phase_change(scenario_id, "analyzing", 0)

                result = await graph.ainvoke(initial_state, config)

                if result.get("status") == "completed":
                    await emitter.emit_report_ready(scenario_id, scenario_id)

            except asyncio.CancelledError:
                await emitter.emit_phase_change(scenario_id, "cancelled", 0)
            except Exception as exc:
                logger.exception("Simulation %s failed", scenario_id)
                await emitter.emit_error(scenario_id, str(exc))
            finally:
                self._running_tasks.pop(scenario_id, None)

        task = asyncio.create_task(_run())
        self._running_tasks[scenario_id] = task

    async def _stop_simulation(self, scenario_id: str) -> None:
        task = self._running_tasks.pop(scenario_id, None)
        if task and not task.done():
            task.cancel()
            logger.info("Simulation %s cancelled", scenario_id)

    async def _apply_decision(self, scenario_id: str, command: dict) -> None:
        if self._graph is None:
            logger.error("Graph not initialized")
            return

        config = {"configurable": {"thread_id": scenario_id}}
        graph = self._graph
        await graph.aupdate_state(
            config,
            {"user_decision": command.get("chosen_action")},
        )
        await graph.ainvoke(None, config)

    async def _resume_simulation(self, scenario_id: str) -> None:
        if self._graph is None:
            logger.error("Graph not initialized")
            return

        graph = self._graph
        config = {"configurable": {"thread_id": scenario_id}}
        await graph.ainvoke(None, config)
        logger.info("Simulation %s resumed", scenario_id)

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

                if result.get("status") == "completed":
                    await emitter.emit_report_ready(branch_id, branch_id)
            except Exception as exc:
                logger.exception("What-if branch %s failed", branch_id)
                await emitter.emit_error(branch_id, str(exc))

        task = asyncio.create_task(_run_branch())
        self._running_tasks[branch_id] = task
