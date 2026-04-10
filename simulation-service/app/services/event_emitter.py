from __future__ import annotations

import json
import logging
from typing import Any

import asyncpg

from app.config import settings

logger = logging.getLogger(__name__)

_CHANNEL = "sim_events"
_PAYLOAD_LIMIT = 7000


class SimulationEventEmitter:
    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    async def _emit(self, event: dict[str, Any]) -> None:
        payload = json.dumps(event, ensure_ascii=False)
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """INSERT INTO simulation_events (scenario_id, event_type, payload)
                   VALUES ($1, $2, $3)
                   RETURNING sequence_num""",
                event.get("scenario_id", ""),
                event.get("type", "unknown"),
                payload,
            )
            event["sequence_num"] = row["sequence_num"]
            notify_payload = json.dumps(event, ensure_ascii=False)
            if len(notify_payload.encode("utf-8")) > _PAYLOAD_LIMIT:
                ref = json.dumps({"type": "event_ref", "event_id": str(row["sequence_num"])})
                await conn.execute("SELECT pg_notify($1, $2)", _CHANNEL, ref)
            else:
                await conn.execute("SELECT pg_notify($1, $2)", _CHANNEL, notify_payload)

    async def emit_phase_change(
        self, scenario_id: str, phase: str, progress: float,
    ) -> None:
        await self._emit({
            "type": "phase_change",
            "scenario_id": scenario_id,
            "phase": phase,
            "progress": progress,
        })

    async def emit_round_complete(
        self, scenario_id: str, round_num: int, actions: list, max_tension: float,
    ) -> None:
        await self._emit({
            "type": "round_complete",
            "scenario_id": scenario_id,
            "round": round_num,
            "actions_count": len(actions),
            "max_tension": max_tension,
            "phase": "simulating",
        })

    async def emit_agent_action(
        self, scenario_id: str, round_num: int, action: dict,
    ) -> None:
        await self._emit({
            "type": "agent_action",
            "scenario_id": scenario_id,
            "round": round_num,
            **action,
        })

    async def emit_intervention_required(
        self, scenario_id: str, decision_point: dict,
    ) -> None:
        await self._emit({
            "type": "intervention_required",
            "scenario_id": scenario_id,
            "decision_point": decision_point,
        })

    async def emit_geopolitical_event(
        self, scenario_id: str, round_num: int,
        trigger_type: str, events: list[dict],
    ) -> None:
        await self._emit({
            "type": "geopolitical_event",
            "scenario_id": scenario_id,
            "round": round_num,
            "trigger_type": trigger_type,
            "events": events[:5],
        })

    async def emit_checkpoint_reached(
        self, scenario_id: str, step: str, state_snapshot: dict,
    ) -> None:
        await self._emit({
            "type": "checkpoint_reached",
            "scenario_id": scenario_id,
            "step": step,
            "state": state_snapshot,
        })

    async def emit_report_ready(self, scenario_id: str, report_id: str) -> None:
        await self._emit({
            "type": "report_ready",
            "scenario_id": scenario_id,
            "report_id": report_id,
        })

    async def store_geopolitics_events(
        self, scenario_id: str, events: list[dict],
    ) -> int:
        """Persist DecisionEngine events into geopolitics_events table."""
        if not events:
            return 0
        async with self._pool.acquire() as conn:
            for idx, evt in enumerate(events):
                target_ids = evt.get("target_actor_ids", [])
                target_str = (
                    ",".join(target_ids) if isinstance(target_ids, list) else str(target_ids)
                )
                await conn.execute(
                    """INSERT INTO geopolitics_events
                       (id, scenario_id, action_type, actor_id, target_actor_ids,
                        content, magnitude, round_number, event_at)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
                       ON CONFLICT DO NOTHING""",
                    f"sim_{scenario_id}_{evt.get('round_number', 0)}_{idx}",
                    scenario_id,
                    evt.get("event_type", "unknown"),
                    evt.get("source_actor_id", ""),
                    target_str,
                    (evt.get("description", "") or "")[:4000],
                    evt.get("magnitude", 0.5),
                    evt.get("round_number", 0),
                )
        return len(events)

    async def emit_error(self, scenario_id: str, error: str) -> None:
        await self._emit({
            "type": "error",
            "scenario_id": scenario_id,
            "error": error,
        })


_emitter: SimulationEventEmitter | None = None


async def init_emitter() -> SimulationEventEmitter:
    global _emitter
    pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=3)
    _emitter = SimulationEventEmitter(pool)
    return _emitter


def get_emitter() -> SimulationEventEmitter:
    assert _emitter is not None, "Event emitter not initialized"
    return _emitter
