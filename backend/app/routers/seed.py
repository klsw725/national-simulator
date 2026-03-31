import json
import logging
import uuid
from datetime import datetime, timezone

import asyncpg
import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from app.clients.shadowbroker import ShadowBrokerClient
from app.database import get_db, get_db_tx
from app.models.decision_point import DecisionOption, DecisionPointResponse
from app.models.scenario import SimulationParams
from app.models.seed import SeedMetadata, SeedResponse
from app.routers._helpers import get_sb_client, row_to_decision_point, row_to_seed_response
from app.services.action_logger import ActionLogger
from app.services.param_recommender import recommend_params
from app.services.seed_generator import SeedGenerator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scenario", tags=["seed"])


def _not_impl(prd: str) -> JSONResponse:
    return JSONResponse(
        status_code=501,
        content={"detail": f"Not implemented. See {prd}."},
    )


@router.post("/{scenario_id}/seed", response_model=SeedResponse, status_code=201)
async def generate_seed(
    scenario_id: str,
    sb_client: ShadowBrokerClient = Depends(get_sb_client),
    conn: asyncpg.Connection = Depends(get_db_tx),
):
    """시드 문서를 생성하고 저장한다."""
    scenario = await conn.fetchrow("SELECT * FROM scenarios WHERE id = $1", scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    existing = await conn.fetchrow("SELECT * FROM seeds WHERE scenario_id = $1", scenario_id)
    if existing:
        return row_to_seed_response(existing)

    generator = SeedGenerator(sb_client)

    bbox = json.loads(scenario["region_bbox"])
    question = scenario["question"]
    region_name = scenario["region_name"]

    raw_params = scenario["simulation_params"] if "simulation_params" in scenario else "{}"
    sim_params = SimulationParams.model_validate_json(raw_params or "{}")

    try:
        await conn.execute(
            "UPDATE scenarios SET seed_status = 'generating', updated_at = $1 WHERE id = $2",
            datetime.now(timezone.utc).isoformat(),
            scenario_id,
        )

        result = await generator.generate(
            bbox=bbox,
            question=question,
            region_name=region_name,
            web_search_enabled=sim_params.web_search_enabled,
        )
    except (httpx.HTTPError, ValueError) as e:
        logger.exception("Seed generation failed for scenario %s", scenario_id)
        await conn.execute(
            "UPDATE scenarios SET seed_status = 'failed', updated_at = $1 WHERE id = $2",
            datetime.now(timezone.utc).isoformat(),
            scenario_id,
        )
        raise HTTPException(status_code=500, detail="Seed generation failed") from e

    seed_id = f"seed_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()

    await conn.execute(
        "INSERT INTO seeds (id, scenario_id, text, metadata, created_at) VALUES ($1, $2, $3, $4, $5)",
        seed_id,
        scenario_id,
        result["text"],
        json.dumps(result["metadata"], ensure_ascii=False),
        now,
    )
    await conn.execute(
        "UPDATE scenarios SET seed_status = 'completed', updated_at = $1 WHERE id = $2",
        now,
        scenario_id,
    )

    used_obs_ids = result["metadata"].get("used_observation_ids", [])
    if used_obs_ids:
        values = [
            (f"so_{uuid.uuid4().hex[:12]}", scenario_id, obs_id, False, now)
            for obs_id in used_obs_ids
        ]
        await conn.executemany(
            "INSERT INTO scenario_observations (id, scenario_id, observation_id, used_in_seed, created_at) VALUES ($1, $2, $3, $4, $5)",
            values,
        )

    await ActionLogger.log(
        "seed.generate",
        scenario_id,
        payload={
            "seed_id": seed_id,
            "vessels_count": result["metadata"].get("vessels_count", 0),
            "resolved_entity_count": result["metadata"].get("resolved_entity_count", 0),
        },
    )

    return SeedResponse(
        id=seed_id,
        scenario_id=scenario_id,
        text=result["text"],
        metadata=SeedMetadata(**result["metadata"]),
        created_at=now,
    )


@router.post("/{scenario_id}/seed_options", status_code=201)
async def generate_seed_options(
    scenario_id: str,
    sb_client: ShadowBrokerClient = Depends(get_sb_client),
    num_options: int = 3,
    conn: asyncpg.Connection = Depends(get_db),
):
    scenario = await conn.fetchrow("SELECT * FROM scenarios WHERE id = $1", scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    if num_options < 2 or num_options > 5:
        raise HTTPException(status_code=400, detail="num_options must be between 2 and 5")

    generator = SeedGenerator(sb_client)

    bbox = json.loads(scenario["region_bbox"])
    question = scenario["question"]
    region_name = scenario["region_name"]

    raw_params = scenario["simulation_params"] if "simulation_params" in scenario else "{}"
    sim_params = SimulationParams.model_validate_json(raw_params or "{}")

    try:
        result = await generator.generate_options(
            bbox=bbox,
            question=question,
            region_name=region_name,
            num_options=num_options,
            web_search_enabled=sim_params.web_search_enabled,
        )
    except (httpx.HTTPError, ValueError) as e:
        logger.exception("Seed options generation failed for scenario %s", scenario_id)
        raise HTTPException(status_code=500, detail="Seed options generation failed") from e

    dp_id = f"dp_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()

    await conn.execute(
        """INSERT INTO decision_points
           (id, scenario_id, type, options, recommended, allow_custom, status, created_at)
           VALUES ($1, $2, 'seed_selection', $3, $4, TRUE, 'pending', $5)""",
        dp_id,
        scenario_id,
        json.dumps(result["options"], ensure_ascii=False),
        result["recommended"],
        now,
    )
    await ActionLogger.log(
        "seed_options.generate",
        scenario_id,
        payload={
            "dp_id": dp_id,
            "options_count": len(result["options"]),
            "recommended": result["recommended"],
        },
    )

    dp_row = await conn.fetchrow("SELECT * FROM decision_points WHERE id = $1", dp_id)
    if not dp_row:
        raise HTTPException(status_code=500, detail="Failed to read back created decision point")

    return {
        "scenario_id": scenario_id,
        "decision_point_id": dp_id,
        "options_count": len(result["options"]),
        "recommended": result["recommended"],
        "decision_point": row_to_decision_point(dp_row),
        "metadata": result["metadata"],
    }


@router.post("/{scenario_id}/recommend_params", status_code=201)
async def recommend_simulation_params(
    scenario_id: str,
    sb_client: ShadowBrokerClient = Depends(get_sb_client),
    conn: asyncpg.Connection = Depends(get_db),
):
    scenario = await conn.fetchrow("SELECT * FROM scenarios WHERE id = $1", scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    generator = SeedGenerator(sb_client)

    bbox = json.loads(scenario["region_bbox"])
    question = scenario["question"]
    region_name = scenario["region_name"]

    raw_params = scenario["simulation_params"] if "simulation_params" in scenario else "{}"
    sim_params = SimulationParams.model_validate_json(raw_params or "{}")

    try:
        ctx = await generator._collect_and_summarize(
            bbox=bbox,
            question=question,
            region_name=region_name,
            web_search_enabled=sim_params.web_search_enabled,
        )
    except (httpx.HTTPError, ValueError) as e:
        logger.exception("OSINT data collection failed for scenario %s", scenario_id)
        raise HTTPException(status_code=500, detail="OSINT data collection failed") from e

    result = recommend_params(ctx["metadata"])

    dp_id = f"dp_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()

    await conn.execute(
        """INSERT INTO decision_points
           (id, scenario_id, type, options, recommended, allow_custom, status, created_at)
           VALUES ($1, $2, 'parameter_recommendation', $3, $4, TRUE, 'pending', $5)""",
        dp_id,
        scenario_id,
        json.dumps(result["options"], ensure_ascii=False),
        result["recommended"],
        now,
    )
    await ActionLogger.log(
        "param_recommendation.generate",
        scenario_id,
        payload={
            "dp_id": dp_id,
            "recommended": result["recommended"],
        },
    )

    dp_row = await conn.fetchrow("SELECT * FROM decision_points WHERE id = $1", dp_id)
    if not dp_row:
        raise HTTPException(status_code=500, detail="Failed to read back created decision point")

    return {
        "scenario_id": scenario_id,
        "decision_point_id": dp_id,
        "recommended": result["recommended"],
        "decision_point": row_to_decision_point(dp_row),
        "metadata": ctx["metadata"],
    }


@router.get("/{scenario_id}/seed", response_model=SeedResponse)
async def get_seed(
    scenario_id: str,
    conn: asyncpg.Connection = Depends(get_db),
):
    row = await conn.fetchrow("SELECT * FROM seeds WHERE scenario_id = $1", scenario_id)
    if not row:
        raise HTTPException(status_code=404, detail="Seed not found for this scenario")
    return row_to_seed_response(row)
