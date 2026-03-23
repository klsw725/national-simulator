import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import asyncpg
from app.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/copilot", tags=["copilot"])


class CopilotChatRequest(BaseModel):
    scenario_id: str
    message: str
    conversation_id: str | None = None


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
    except Exception:
        logger.exception("Copilot chat failed for scenario %s", body.scenario_id)
        raise HTTPException(status_code=502, detail="Copilot LLM 호출 실패")
    return result
