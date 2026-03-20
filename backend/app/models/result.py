from typing import Any

from pydantic import BaseModel


class SimulationResultResponse(BaseModel):
    id: str
    scenario_id: str
    mirofish_simulation_id: str | None = None
    mirofish_project_id: str | None = None
    status: str
    platform: str
    results: dict | None = None
    geojson: dict | None = None
    report: str | None = None
    created_at: str
    completed_at: str | None = None


class CheckpointResponse(BaseModel):
    scenario_id: str
    result_id: str
    status: str
    step: str
    editable: bool
    data: dict[str, Any] | None = None
    pipeline_mode: str = "checkpoint"


class SimulateRequest(BaseModel):
    mode: str = "auto"


class ContinueRequest(BaseModel):
    edits: dict[str, Any] | None = None
