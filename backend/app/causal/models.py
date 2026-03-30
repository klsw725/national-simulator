from __future__ import annotations

from pydantic import BaseModel


class CausalVariable(BaseModel):
    name: str
    description: str
    var_type: str = "continuous"
    domain: tuple[float, float] | None = None


class CausalEdge(BaseModel):
    source: str
    target: str
    edge_type: str = "causes"
    strength: float | None = None
    confidence: float | None = None
    provenance: str = "domain"


class CausalDAG(BaseModel):
    id: str
    scenario_id: str | None = None
    model_type: str
    variables: list[CausalVariable]
    edges: list[CausalEdge]
    fit_metadata: dict | None = None
    created_at: str


class CausalObservation(BaseModel):
    scenario_id: str
    result_id: str
    round_num: int
    variables: dict[str, float]


class InterventionRequest(BaseModel):
    model_id: str
    interventions: dict[str, float]
    target_variables: list[str] | None = None
    num_samples: int = 500


class InterventionResult(BaseModel):
    interventions: dict[str, float]
    targets: dict[str, dict]
    num_samples: int


class CounterfactualRequest(BaseModel):
    model_id: str
    observed: dict[str, float]
    interventions: dict[str, float]


class CounterfactualResult(BaseModel):
    observed: dict[str, float]
    counterfactual: dict[str, float]
    differences: dict[str, float]


class AttributionRequest(BaseModel):
    model_id: str
    target_variable: str


class AttributionResult(BaseModel):
    target_variable: str
    attributions: dict[str, float]
    total_explained: float
    method: str = "intervention_range"


class CausalFitRequest(BaseModel):
    model_id: str
    scenario_id: str | None = None


class CausalExtractRequest(BaseModel):
    text: str
    scenario_id: str | None = None


class CausalExtractResult(BaseModel):
    edges: list[CausalEdge]
    verified: bool


class CausalNarrateRequest(BaseModel):
    model_id: str
    target_variable: str
    context: str = ""


class CausalNarrateResult(BaseModel):
    narrative: str
    paths_used: int
    confidence: str
