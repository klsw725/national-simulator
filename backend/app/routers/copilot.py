import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import asyncpg
from app.clients.mirofish import MiroFishClient
from app.database import get_db

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
    scenario = await conn.fetchrow("SELECT id FROM scenarios WHERE id = $1", body.scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    from app.services.copilot import CopilotService

    service = CopilotService()
    try:
        result = await service.chat(
            scenario_id=body.scenario_id,
            message=body.message,
            conversation_id=body.conversation_id,
        )
    except (httpx.HTTPError, ValueError) as e:
        logger.exception("Copilot chat failed for scenario %s", body.scenario_id)
        raise HTTPException(status_code=502, detail="Copilot LLM 호출 실패") from e
    return result


@router.post("/env-status")
async def get_env_status(
    body: EnvRequest,
    conn: asyncpg.Connection = Depends(get_db),
):
    row = await conn.fetchrow(
        "SELECT mirofish_simulation_id FROM simulation_results WHERE scenario_id = $1 ORDER BY created_at DESC LIMIT 1",
        body.scenario_id,
    )
    if not row or not row["mirofish_simulation_id"]:
        raise HTTPException(status_code=404, detail="Simulation environment not found")

    from app.config import settings
    client = MiroFishClient(settings.mirofish_url)
    try:
        return await client.get_env_status(row["mirofish_simulation_id"])
    except httpx.HTTPError as e:
        logger.exception("Env status failed for scenario %s", body.scenario_id)
        raise HTTPException(status_code=502, detail="환경 상태 조회 실패") from e
    finally:
        await client.close()


@router.post("/interview")
async def interview_agent(
    body: InterviewAgentRequest,
    conn: asyncpg.Connection = Depends(get_db),
):
    row = await conn.fetchrow(
        "SELECT mirofish_simulation_id FROM simulation_results WHERE scenario_id = $1 ORDER BY created_at DESC LIMIT 1",
        body.scenario_id,
    )
    if not row or not row["mirofish_simulation_id"]:
        raise HTTPException(status_code=404, detail="Simulation environment not found")

    from app.config import settings
    client = MiroFishClient(settings.mirofish_url)
    try:
        return await client.interview_agent(
            row["mirofish_simulation_id"],
            body.agent_id,
            body.prompt,
            platform=body.platform,
        )
    except httpx.HTTPError as e:
        logger.exception("Interview agent failed for scenario %s", body.scenario_id)
        raise HTTPException(status_code=502, detail="에이전트 인터뷰 실패") from e
    finally:
        await client.close()


@router.post("/interview/all")
async def interview_all_agents(
    body: InterviewAllRequest,
    conn: asyncpg.Connection = Depends(get_db),
):
    row = await conn.fetchrow(
        "SELECT mirofish_simulation_id FROM simulation_results WHERE scenario_id = $1 ORDER BY created_at DESC LIMIT 1",
        body.scenario_id,
    )
    if not row or not row["mirofish_simulation_id"]:
        raise HTTPException(status_code=404, detail="Simulation environment not found")

    from app.config import settings
    client = MiroFishClient(settings.mirofish_url)
    try:
        return await client.interview_all_agents(
            row["mirofish_simulation_id"],
            body.prompt,
            platform=body.platform,
        )
    except httpx.HTTPError as e:
        logger.exception("Interview all failed for scenario %s", body.scenario_id)
        raise HTTPException(status_code=502, detail="전체 에이전트 인터뷰 실패") from e
    finally:
        await client.close()


@router.post("/close-env")
async def close_simulation_env(
    body: EnvRequest,
    conn: asyncpg.Connection = Depends(get_db),
):
    row = await conn.fetchrow(
        "SELECT mirofish_simulation_id FROM simulation_results WHERE scenario_id = $1 ORDER BY created_at DESC LIMIT 1",
        body.scenario_id,
    )
    if not row or not row["mirofish_simulation_id"]:
        raise HTTPException(status_code=404, detail="Simulation environment not found")

    from app.config import settings
    client = MiroFishClient(settings.mirofish_url)
    try:
        return await client.close_env(row["mirofish_simulation_id"])
    except httpx.HTTPError as e:
        logger.exception("Close env failed for scenario %s", body.scenario_id)
        raise HTTPException(status_code=502, detail="환경 종료 실패") from e
    finally:
        await client.close()
