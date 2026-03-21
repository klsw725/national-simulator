from pydantic import BaseModel


class SeedMetadata(BaseModel):
    vessels_count: int = 0
    actors_identified: list[str] = []
    military_flights_count: int = 0
    satellites_count: int = 0
    gdelt_events_count: int = 0
    tension_score: float = 0.0
    osint_sources_used: int = 0
    data_timestamp: str = ""


class SeedResponse(BaseModel):
    id: str
    scenario_id: str
    text: str
    metadata: SeedMetadata
    created_at: str
