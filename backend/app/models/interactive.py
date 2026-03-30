from __future__ import annotations

from pydantic import BaseModel, Field


class InteractiveSimulationConfig(BaseModel):
    pause_at_rounds: list[int] = Field(default_factory=list)
    auto_pause_on_tension: bool = True
    tension_threshold: float = 0.7
    max_pause_duration_minutes: int = 30


class InjectEventRequest(BaseModel):
    event_type: str = "news_announcement"
    content: str
    target_agents: list[str] = Field(default_factory=lambda: ["all"])


class InteractiveStatus(BaseModel):
    scenario_id: str
    simulation_status: str
    current_round: int = 0
    max_rounds: int = 10
    is_paused: bool = False
    pause_reason: str | None = None
    injected_events_count: int = 0
    tension_alerts: int = 0


# ── What-If Counterfactual Replay (v7-whatif-counterfactual) ──


class WhatIfCreateRequest(BaseModel):
    modification: str
    branch_point_round: int | None = None
    execution_mode: str = "full_replay"
    max_rounds_override: int | None = None


class WhatIfBranch(BaseModel):
    id: str
    scenario_id: str
    parent_result_id: str
    branch_result_id: str | None = None
    branch_point_round: int | None = None
    modification: str
    execution_mode: str = "full_replay"
    world_model_strategy: str = "regenerate"
    status: str = "pending"
    comparison_data: dict | None = None
    created_at: str
    completed_at: str | None = None


class WhatIfComparison(BaseModel):
    branch_id: str
    tension_advantage: float = 0.0
    tension_curves: dict = Field(default_factory=lambda: {"original": [], "branch": []})
    step_variance: dict = Field(default_factory=lambda: {"original": 0.0, "branch": 0.0})
    slope_variance: dict = Field(default_factory=lambda: {"original": 0.0, "branch": 0.0})
    actor_diff: dict = Field(default_factory=lambda: {"only_original": [], "only_branch": [], "common": []})
    action_count_delta: int = 0
    geopolitics_delta: int = 0
    causal_attribution: dict | None = None
