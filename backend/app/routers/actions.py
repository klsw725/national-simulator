from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.action_logger import ActionLogger

router = APIRouter(prefix="/api/actions", tags=["actions"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------
class ActionCreateRequest(BaseModel):
    action_type: str
    actor: str = "system"
    actor_role: str = "analyst"
    scenario_id: str | None = None
    payload: dict[str, Any] | None = None


class ActionDecisionRequest(BaseModel):
    decided_by: str


# ---------------------------------------------------------------------------
# POST /api/actions — create an action (goes through RBAC + approval rules)
# ---------------------------------------------------------------------------
@router.post("", status_code=201)
async def create_action(data: ActionCreateRequest):
    try:
        result = await ActionLogger.submit(
            action_type=data.action_type,
            actor=data.actor,
            actor_role=data.actor_role,
            scenario_id=data.scenario_id,
            payload=data.payload,
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    return result


# ---------------------------------------------------------------------------
# GET /api/actions — list actions with optional filters
# ---------------------------------------------------------------------------
@router.get("")
async def list_actions(
    status: str | None = None,
    action_type: str | None = None,
    scenario_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
):
    events = await ActionLogger.query(
        scenario_id=scenario_id,
        action_type=action_type,
        status=status,
        limit=limit,
        offset=offset,
    )
    return {"count": len(events), "events": events}


# ---------------------------------------------------------------------------
# GET /api/actions/{action_id} — get single action
# ---------------------------------------------------------------------------
@router.get("/{action_id}")
async def get_action(action_id: str):
    action = await ActionLogger.get_by_id(action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    return action


# ---------------------------------------------------------------------------
# POST /api/actions/{action_id}/approve — approve a pending action
# ---------------------------------------------------------------------------
@router.post("/{action_id}/approve")
async def approve_action(action_id: str, data: ActionDecisionRequest):
    try:
        result = await ActionLogger.approve(action_id, data.decided_by)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


# ---------------------------------------------------------------------------
# POST /api/actions/{action_id}/reject — reject a pending action
# ---------------------------------------------------------------------------
@router.post("/{action_id}/reject")
async def reject_action(action_id: str, data: ActionDecisionRequest):
    try:
        result = await ActionLogger.reject(action_id, data.decided_by)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


# ---------------------------------------------------------------------------
# POST /api/actions/{action_id}/compensate — rollback via compensation
# ---------------------------------------------------------------------------
@router.post("/{action_id}/compensate")
async def compensate_action(action_id: str, data: ActionDecisionRequest):
    try:
        result = await ActionLogger.compensate(action_id, data.decided_by)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result
