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


async def _scenario_exists(scenario_id: str) -> bool:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM scenarios WHERE id = $1",
            scenario_id,
        )
    return bool(row)


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
        "tools_used": [],
        "suggestions": [],
    }


@router.post("/env-status")
async def get_env_status(body: EnvRequest):
    if not await _scenario_exists(body.scenario_id):
        raise HTTPException(status_code=404, detail="Scenario not found")

    return {
        "simulation_id": body.scenario_id,
        "env_alive": False,
        "reddit_available": False,
        "twitter_available": False,
        "message": "에이전트 대화 ENV는 아직 연결되지 않았습니다. 현재는 코파일럿만 사용할 수 있습니다.",
    }


@router.post("/interview")
async def interview_agent(body: InterviewAgentRequest):
    if not await _scenario_exists(body.scenario_id):
        raise HTTPException(status_code=404, detail="Scenario not found")
    raise HTTPException(status_code=503, detail="에이전트 인터뷰 ENV가 아직 연결되지 않았습니다. 코파일럿 모드를 사용하세요.")


@router.post("/interview/all")
async def interview_all_agents(body: InterviewAllRequest):
    if not await _scenario_exists(body.scenario_id):
        raise HTTPException(status_code=404, detail="Scenario not found")
    raise HTTPException(status_code=503, detail="전체 에이전트 인터뷰 ENV가 아직 연결되지 않았습니다. 코파일럿 모드를 사용하세요.")


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
