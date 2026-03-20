from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/scenario", tags=["simulation"])


def _not_impl(prd: str) -> JSONResponse:
    return JSONResponse(
        status_code=501,
        content={"detail": f"Not implemented. See {prd}."},
    )


@router.post("/{scenario_id}/seed")
async def generate_seed(scenario_id: str):
    return _not_impl("PRD 3 (seed-generation)")


@router.get("/{scenario_id}/seed")
async def get_seed(scenario_id: str):
    return _not_impl("PRD 3 (seed-generation)")


@router.post("/{scenario_id}/simulate")
async def start_simulation(scenario_id: str):
    return _not_impl("PRD 4 (simulation-orchestration)")


@router.get("/{scenario_id}/status")
async def get_simulation_status(scenario_id: str):
    return _not_impl("PRD 4 (simulation-orchestration)")


@router.get("/{scenario_id}/results")
async def get_simulation_results(scenario_id: str):
    return _not_impl("PRD 4 (simulation-orchestration)")


@router.get("/{scenario_id}/geojson")
async def get_geojson(scenario_id: str):
    return _not_impl("PRD 5 (result-projection)")


@router.get("/{scenario_id}/report")
async def get_report(scenario_id: str):
    return _not_impl("PRD 5 (result-projection)")
