from pydantic import BaseModel, Field


class ScenarioRegion(BaseModel):
    bbox: list[float] = Field(..., min_length=4, max_length=4)
    name: str


class ScenarioCreate(BaseModel):
    name: str
    region: ScenarioRegion
    question: str
    max_rounds: int = Field(default=10, ge=1, le=30)
    data_sources: list[str] = Field(default=["ships", "geopolitics"])


class ScenarioCreatedResponse(BaseModel):
    id: str
    status: str
    seed_status: str
    simulation_status: str


class ScenarioResponse(BaseModel):
    id: str
    name: str
    region_bbox: list[float]
    region_name: str
    question: str
    max_rounds: int
    data_sources: list[str]
    status: str
    seed_status: str
    simulation_status: str
    created_at: str
    updated_at: str
