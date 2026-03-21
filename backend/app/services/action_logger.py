from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from app.database import get_pool

# ---------------------------------------------------------------------------
# Role hierarchy: higher number = more privilege
# ---------------------------------------------------------------------------
ROLE_LEVEL = {"viewer": 0, "analyst": 1, "admin": 2, "system": 3}

# ---------------------------------------------------------------------------
# Approval rules per action_type
#   - auto_approve : executes immediately if actor has sufficient role
#   - manual       : goes to pending queue, needs explicit approve call
#   - min_role     : minimum role required to create the action
# ---------------------------------------------------------------------------
APPROVAL_RULES: dict[str, dict[str, Any]] = {
    # Auto-approve actions (analyst or higher)
    "scenario.create":     {"mode": "auto_approve", "min_role": "analyst"},
    "scenario.delete":     {"mode": "auto_approve", "min_role": "analyst"},
    "entity.tag":          {"mode": "auto_approve", "min_role": "analyst"},
    "entity.annotate":     {"mode": "auto_approve", "min_role": "analyst"},
    "seed.inject":         {"mode": "auto_approve", "min_role": "analyst"},
    "simulation.trigger":  {"mode": "auto_approve", "min_role": "analyst"},
    "simulation.start":    {"mode": "auto_approve", "min_role": "analyst"},
    "simulation.continue": {"mode": "auto_approve", "min_role": "analyst"},
    "seed.generate":       {"mode": "auto_approve", "min_role": "analyst"},
    # Manual-approval actions
    "entity.merge":        {"mode": "manual", "min_role": "analyst"},
    "seed.remove":         {"mode": "manual", "min_role": "analyst"},
    # Admin-only actions
    "scenario.archive":    {"mode": "auto_approve", "min_role": "admin"},
    "scenario.update":     {"mode": "auto_approve", "min_role": "admin"},
}

# Pipeline actions logged by the system — always auto-execute
_SYSTEM_ACTIONS = {
    "pipeline.ontology",
    "pipeline.graph_build",
    "pipeline.prepare",
    "pipeline.run_complete",
    "pipeline.report",
    "pipeline.failed",
    "snapshot.create",
}


def _check_role(actor_role: str, min_role: str) -> bool:
    return ROLE_LEVEL.get(actor_role, -1) >= ROLE_LEVEL.get(min_role, 99)


class ActionLogger:
    """Action layer with RBAC approval rules and compensation (rollback)."""

    # ------------------------------------------------------------------
    # Original log() — kept backward-compatible for existing callers.
    # System/internal actions bypass approval and execute immediately.
    # ------------------------------------------------------------------
    @staticmethod
    async def log(
        action_type: str,
        scenario_id: str | None = None,
        actor: str = "system",
        payload: dict[str, Any] | None = None,
    ) -> str:
        return await ActionLogger._insert(
            action_type=action_type,
            scenario_id=scenario_id,
            actor=actor,
            actor_role="system",
            status="executed",
            payload=payload,
        )

    # ------------------------------------------------------------------
    # submit() — new entry point that enforces RBAC + approval rules.
    # Returns the action record dict (including status).
    # ------------------------------------------------------------------
    @staticmethod
    async def submit(
        action_type: str,
        actor: str,
        actor_role: str,
        scenario_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        rule = APPROVAL_RULES.get(action_type)

        # Unknown action type — reject
        if rule is None and action_type not in _SYSTEM_ACTIONS:
            raise PermissionError(f"Unknown action type: {action_type}")

        # System actions always execute
        if action_type in _SYSTEM_ACTIONS:
            action_id = await ActionLogger._insert(
                action_type=action_type,
                scenario_id=scenario_id,
                actor=actor,
                actor_role=actor_role,
                status="executed",
                payload=payload,
            )
            return await ActionLogger._get_or_raise(action_id)

        # Role check
        assert rule is not None
        if not _check_role(actor_role, rule["min_role"]):
            raise PermissionError(
                f"Role '{actor_role}' cannot perform '{action_type}' "
                f"(requires '{rule['min_role']}' or higher)"
            )

        # Determine initial status
        status = "executed" if rule["mode"] == "auto_approve" else "pending"

        action_id = await ActionLogger._insert(
            action_type=action_type,
            scenario_id=scenario_id,
            actor=actor,
            actor_role=actor_role,
            status=status,
            payload=payload,
        )
        return await ActionLogger._get_or_raise(action_id)

    # ------------------------------------------------------------------
    # approve / reject — for pending actions
    # ------------------------------------------------------------------
    @staticmethod
    async def approve(action_id: str, approved_by: str) -> dict[str, Any]:
        action = await ActionLogger.get_by_id(action_id)
        if not action:
            raise ValueError(f"Action {action_id} not found")
        if action["status"] != "pending":
            raise ValueError(f"Action {action_id} is not pending (status={action['status']})")

        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE action_log SET status = 'approved' WHERE id = $1",
                action_id,
            )
        # Log the approval itself
        await ActionLogger._insert(
            action_type=f"{action['action_type']}.approved",
            scenario_id=action["scenario_id"],
            actor=approved_by,
            actor_role="admin",
            status="executed",
            payload={"approved_action_id": action_id},
        )
        return await ActionLogger._get_or_raise(action_id)

    @staticmethod
    async def reject(action_id: str, rejected_by: str) -> dict[str, Any]:
        action = await ActionLogger.get_by_id(action_id)
        if not action:
            raise ValueError(f"Action {action_id} not found")
        if action["status"] != "pending":
            raise ValueError(f"Action {action_id} is not pending (status={action['status']})")

        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE action_log SET status = 'rejected' WHERE id = $1",
                action_id,
            )
        await ActionLogger._insert(
            action_type=f"{action['action_type']}.rejected",
            scenario_id=action["scenario_id"],
            actor=rejected_by,
            actor_role="admin",
            status="executed",
            payload={"rejected_action_id": action_id},
        )
        return await ActionLogger._get_or_raise(action_id)

    # ------------------------------------------------------------------
    # compensate — rollback by creating a compensation action
    # ------------------------------------------------------------------
    @staticmethod
    async def compensate(action_id: str, compensated_by: str) -> dict[str, Any]:
        action = await ActionLogger.get_by_id(action_id)
        if not action:
            raise ValueError(f"Action {action_id} not found")
        if action["status"] not in ("executed", "approved"):
            raise ValueError(
                f"Action {action_id} cannot be compensated (status={action['status']})"
            )

        # Mark original as compensated
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE action_log SET status = 'compensated' WHERE id = $1",
                action_id,
            )

        # Create the compensation record
        comp_id = await ActionLogger._insert(
            action_type=f"{action['action_type']}.compensate",
            scenario_id=action["scenario_id"],
            actor=compensated_by,
            actor_role="admin",
            status="executed",
            payload={
                "compensated_action_id": action_id,
                "original_payload": action["payload"],
            },
            compensation_for=action_id,
        )
        return await ActionLogger._get_or_raise(comp_id)

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------
    @staticmethod
    async def get_by_id(action_id: str) -> dict[str, Any] | None:
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM action_log WHERE id = $1", action_id)
        return ActionLogger._row_to_dict(row) if row else None

    @staticmethod
    async def query(
        scenario_id: str | None = None,
        action_type: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        conditions: list[str] = []
        params: list[Any] = []
        idx = 1

        if scenario_id:
            conditions.append(f"scenario_id = ${idx}")
            params.append(scenario_id)
            idx += 1
        if action_type:
            conditions.append(f"action_type = ${idx}")
            params.append(action_type)
            idx += 1
        if status:
            conditions.append(f"status = ${idx}")
            params.append(status)
            idx += 1

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"SELECT * FROM action_log {where} ORDER BY created_at DESC LIMIT ${idx} OFFSET ${idx + 1}"
        params.extend([limit, offset])

        pool = get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
        return [ActionLogger._row_to_dict(row) for row in rows]

    @staticmethod
    async def _get_or_raise(action_id: str) -> dict[str, Any]:
        result = await ActionLogger.get_by_id(action_id)
        if result is None:
            raise ValueError(f"Action {action_id} not found after insert")
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    async def _insert(
        action_type: str,
        scenario_id: str | None,
        actor: str,
        actor_role: str,
        status: str,
        payload: dict[str, Any] | None,
        compensation_for: str | None = None,
    ) -> str:
        action_id = f"act_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO action_log
                   (id, scenario_id, action_type, actor, actor_role, status, payload, compensation_for, created_at)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)""",
                action_id,
                scenario_id,
                action_type,
                actor,
                actor_role,
                status,
                json.dumps(payload, ensure_ascii=False) if payload else None,
                compensation_for,
                now,
            )
        return action_id

    @staticmethod
    def _row_to_dict(row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "scenario_id": row["scenario_id"],
            "action_type": row["action_type"],
            "actor": row["actor"],
            "actor_role": row.get("actor_role", "system"),
            "status": row.get("status", "executed"),
            "payload": json.loads(row["payload"]) if row["payload"] else None,
            "compensation_for": row.get("compensation_for"),
            "created_at": row["created_at"],
        }
