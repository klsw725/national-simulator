from enum import Enum

from pydantic import BaseModel, Field


class DecisionPointType(str, Enum):
    SEED_SELECTION = "seed_selection"
    ACTOR_CONFIGURATION = "actor_configuration"
    PARAMETER_RECOMMENDATION = "parameter_recommendation"
    GEOPOLITICS_ACTOR_RESPONSE = "geopolitics_actor_response"
    GEOPOLITICS_DIRECTION = "geopolitics_direction"


class DecisionOption(BaseModel):
    id: str
    label: str
    description: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    data: dict = Field(default_factory=dict)


class DecisionPointCreate(BaseModel):
    type: DecisionPointType
    options: list[DecisionOption] = Field(min_length=1)
    recommended: str
    allow_custom: bool = True


class DecisionPointResponse(BaseModel):
    id: str
    scenario_id: str
    type: DecisionPointType
    options: list[DecisionOption]
    recommended: str
    allow_custom: bool
    status: str  # "pending" | "resolved"
    selected_option_id: str | None = None
    custom_data: dict | None = None
    created_at: str
    resolved_at: str | None = None


class DecisionPointResolveRequest(BaseModel):
    selected_option_id: str | None = None
    custom_data: dict | None = None
