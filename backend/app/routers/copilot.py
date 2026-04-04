import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import asyncpg
from app.database import get_db, get_pool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/copilot", tags=["copilot"])


class CopilotChatRequest(BaseModel):
    scenario_id: str
    message: str
    conversation_id: str | None = None


class EnvRequest(BaseModel):
    scenario_id: str


class InterviewAgentRequest(BaseModel):
    scenario_id: str
    agent_id: int
    prompt: str
    platform: str | None = None


class InterviewAllRequest(BaseModel):
    scenario_id: str
    prompt: str
    platform: str | None = None


@router.post("/chat")
async def copilot_chat(
    body: CopilotChatRequest,
    conn: asyncpg.Connection = Depends(get_db),
):
    row = await conn.fetchrow(
        "SELECT id FROM scenarios WHERE id = $1", body.scenario_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Scenario not found")

    return {
        "response": f"[Copilot] 시나리오 {body.scenario_id}에 대한 분석을 준비 중입니다.",
        "scenario_id": body.scenario_id,
        "conversation_id": body.conversation_id,
    }


@router.post("/env-status")
async def get_env_status(body: EnvRequest):
    pool = get_pool()
    async with pool.acquire() as conn:
        latest = await conn.fetchrow(
            """SELECT event_type, payload FROM simulation_events
               WHERE scenario_id = $1 ORDER BY sequence_num DESC LIMIT 1""",
            body.scenario_id,
        )
    if not latest:
        raise HTTPException(status_code=404, detail="Simulation environment not found")

    payload = json.loads(latest["payload"]) if isinstance(latest["payload"], str) else (latest["payload"] or {})
    return {"status": "active", "phase": payload.get("phase", "unknown"), "scenario_id": body.scenario_id}


@router.post("/interview")
async def interview_agent(body: InterviewAgentRequest):
    return {
        "agent_id": body.agent_id,
        "response": f"[v2 stub] 에이전트 {body.agent_id} 인터뷰 기능은 Simulation Service에서 직접 제공 예정입니다.",
    }


@router.post("/interview/all")
async def interview_all_agents(body: InterviewAllRequest):
    return {
        "responses": [],
        "message": "[v2 stub] 전체 에이전트 인터뷰 기능은 Simulation Service에서 직접 제공 예정입니다.",
    }


@router.post("/close-env")
async def close_simulation_env(body: EnvRequest):
    pool = get_pool()
    command = json.dumps({
        "type": "stop_simulation",
        "scenario_id": body.scenario_id,
    }, ensure_ascii=False)
    async with pool.acquire() as conn:
        await conn.execute("SELECT pg_notify($1, $2)", "sim_commands", command)
    return {"status": "closed", "scenario_id": body.scenario_id}
