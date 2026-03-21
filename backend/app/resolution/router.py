from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.resolution.resolver import Resolver

router = APIRouter(prefix="/api/resolution", tags=["resolution"])

_resolver = Resolver()


class MergeRequest(BaseModel):
    observation_id: str
    target_stix_id: str
    decided_by: str


class DecisionRequest(BaseModel):
    decided_by: str


# GET /api/resolution/queue — pending candidates for manual review
@router.get("/queue")
async def get_review_queue(
    observation_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
):
    candidates = await _resolver.get_candidates(
        observation_id=observation_id,
        status="pending",
        limit=limit,
        offset=offset,
    )
    return {"count": len(candidates), "candidates": candidates}


# GET /api/resolution/decisions — resolution decision history
@router.get("/decisions")
async def get_decisions(
    observation_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
):
    decisions = await _resolver.get_decisions(
        observation_id=observation_id,
        limit=limit,
        offset=offset,
    )
    return {"count": len(decisions), "decisions": decisions}


# POST /api/resolution/{candidate_id}/accept
@router.post("/{candidate_id}/accept")
async def accept_candidate(candidate_id: str, data: DecisionRequest):
    try:
        decision = await _resolver.accept_candidate(candidate_id, data.decided_by)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return decision


# POST /api/resolution/{candidate_id}/reject
@router.post("/{candidate_id}/reject")
async def reject_candidate(candidate_id: str, data: DecisionRequest):
    try:
        decision = await _resolver.reject_candidate(candidate_id, data.decided_by)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return decision


# POST /api/resolution/merge — direct merge without candidate
@router.post("/merge")
async def merge_entities(data: MergeRequest):
    decision = await _resolver.merge_entities(
        observation_id=data.observation_id,
        target_stix_id=data.target_stix_id,
        decided_by=data.decided_by,
    )
    return decision
