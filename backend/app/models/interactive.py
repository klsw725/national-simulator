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
