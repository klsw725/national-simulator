from __future__ import annotations

import asyncpg

from app.config import settings

_pool: asyncpg.Pool | None = None

# Deprecated fallback inline DDL. Preferred path is Alembic migrations via:
# `uv run alembic upgrade head`.
SCHEMA = """\
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS scenarios (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    region_bbox TEXT NOT NULL,
    region_name TEXT NOT NULL,
    question TEXT NOT NULL,
    max_rounds INTEGER DEFAULT 10,
    data_sources TEXT NOT NULL,
    status TEXT DEFAULT 'created',
    seed_status TEXT DEFAULT 'pending',
    simulation_status TEXT DEFAULT 'pending',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS seeds (
    id TEXT PRIMARY KEY,
    scenario_id TEXT NOT NULL REFERENCES scenarios(id),
    text TEXT NOT NULL,
    metadata TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS simulation_results (
    id TEXT PRIMARY KEY,
    scenario_id TEXT NOT NULL REFERENCES scenarios(id),
    mirofish_simulation_id TEXT,
    mirofish_project_id TEXT,
    graph_task_id TEXT,
    graph_id TEXT,
    status TEXT DEFAULT 'pending',
    platform TEXT DEFAULT 'twitter',
    pipeline_mode TEXT DEFAULT 'auto',
    checkpoint_data TEXT,
    results TEXT,
    geojson TEXT,
    report TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS stix_objects (
    id TEXT PRIMARY KEY,
    stix_id TEXT UNIQUE NOT NULL,
    object_type TEXT NOT NULL,
    stix_json TEXT NOT NULL,
    confidence REAL DEFAULT 0.0,
    source TEXT,
    branch_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scenario_snapshots (
    id TEXT PRIMARY KEY,
    scenario_id TEXT NOT NULL REFERENCES scenarios(id),
    fast_data TEXT,
    slow_data TEXT,
    snapshot_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS action_log (
    id TEXT PRIMARY KEY,
    scenario_id TEXT,
    action_type TEXT NOT NULL,
    actor TEXT DEFAULT 'system',
    actor_role TEXT DEFAULT 'system',
    status TEXT DEFAULT 'executed',
    payload TEXT,
    compensation_for TEXT,
    created_at TEXT NOT NULL
);

ALTER TABLE action_log ADD COLUMN IF NOT EXISTS actor_role TEXT DEFAULT 'system';
ALTER TABLE action_log ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'executed';
ALTER TABLE action_log ADD COLUMN IF NOT EXISTS compensation_for TEXT;

ALTER TABLE scenarios ADD COLUMN IF NOT EXISTS simulation_params TEXT DEFAULT '{}';

CREATE TABLE IF NOT EXISTS observations (
    id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    raw_data TEXT NOT NULL,
    geom geometry(Point, 4326),
    observed_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ontology_versions (
    id TEXT PRIMARY KEY,
    version TEXT NOT NULL,
    schema_hash TEXT NOT NULL,
    schema_json TEXT NOT NULL,
    change_summary TEXT,
    is_breaking BOOLEAN DEFAULT FALSE,
    created_by TEXT DEFAULT 'system',
    created_at TEXT NOT NULL
);

ALTER TABLE simulation_results ADD COLUMN IF NOT EXISTS ontology_version TEXT;

CREATE TABLE IF NOT EXISTS geopolitics_events (
    id TEXT PRIMARY KEY,
    scenario_id TEXT,
    simulation_result_id TEXT,
    action_type TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    target_actor_ids TEXT,
    content TEXT,
    magnitude REAL DEFAULT 0.5,
    round_number INTEGER DEFAULT 0,
    event_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS resolution_candidates (
    id TEXT PRIMARY KEY,
    observation_id TEXT NOT NULL,
    candidate_stix_id TEXT NOT NULL,
    match_score REAL NOT NULL,
    match_strategy TEXT NOT NULL,
    match_reason TEXT,
    status TEXT DEFAULT 'pending',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS resolution_decisions (
    id TEXT PRIMARY KEY,
    observation_id TEXT NOT NULL,
    resolved_stix_id TEXT NOT NULL,
    decision_type TEXT NOT NULL,
    decided_by TEXT NOT NULL,
    confidence REAL NOT NULL,
    reason TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_stix_objects_type ON stix_objects(object_type);
CREATE INDEX IF NOT EXISTS idx_stix_objects_stix_id ON stix_objects(stix_id);
CREATE INDEX IF NOT EXISTS idx_stix_objects_branch ON stix_objects(branch_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_scenario ON scenario_snapshots(scenario_id);
CREATE INDEX IF NOT EXISTS idx_action_log_scenario ON action_log(scenario_id);
CREATE INDEX IF NOT EXISTS idx_action_log_type ON action_log(action_type);
CREATE INDEX IF NOT EXISTS idx_action_log_created ON action_log(created_at);
CREATE INDEX IF NOT EXISTS idx_observations_geom ON observations USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_observations_source ON observations(source_type, source_id);
CREATE INDEX IF NOT EXISTS idx_observations_time ON observations(observed_at);
CREATE INDEX IF NOT EXISTS idx_resolution_candidates_obs ON resolution_candidates(observation_id);
CREATE INDEX IF NOT EXISTS idx_resolution_candidates_stix ON resolution_candidates(candidate_stix_id);
CREATE INDEX IF NOT EXISTS idx_resolution_candidates_status ON resolution_candidates(status);
CREATE INDEX IF NOT EXISTS idx_resolution_decisions_obs ON resolution_decisions(observation_id);
CREATE INDEX IF NOT EXISTS idx_resolution_decisions_stix ON resolution_decisions(resolved_stix_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_ontology_versions_version ON ontology_versions(version);
CREATE INDEX IF NOT EXISTS idx_ontology_versions_hash ON ontology_versions(schema_hash);
CREATE INDEX IF NOT EXISTS idx_geopolitics_events_scenario ON geopolitics_events(scenario_id);
CREATE INDEX IF NOT EXISTS idx_geopolitics_events_actor ON geopolitics_events(actor_id);
CREATE INDEX IF NOT EXISTS idx_geopolitics_events_type ON geopolitics_events(action_type);

CREATE TABLE IF NOT EXISTS scenario_observations (
    id TEXT PRIMARY KEY,
    scenario_id TEXT NOT NULL,
    observation_id TEXT NOT NULL,
    used_in_seed BOOLEAN DEFAULT FALSE,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_scenario_obs_scenario ON scenario_observations(scenario_id);
CREATE INDEX IF NOT EXISTS idx_scenario_obs_observation ON scenario_observations(observation_id);

CREATE TABLE IF NOT EXISTS decision_points (
    id TEXT PRIMARY KEY,
    scenario_id TEXT NOT NULL REFERENCES scenarios(id),
    type TEXT NOT NULL,
    options TEXT NOT NULL,
    recommended TEXT NOT NULL,
    allow_custom BOOLEAN DEFAULT TRUE,
    status TEXT DEFAULT 'pending',
    selected_option_id TEXT,
    custom_data TEXT,
    created_at TEXT NOT NULL,
    resolved_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_decision_points_scenario ON decision_points(scenario_id);
CREATE INDEX IF NOT EXISTS idx_decision_points_status ON decision_points(status);

CREATE TABLE IF NOT EXISTS briefings (
    id TEXT PRIMARY KEY,
    scenario_id TEXT NOT NULL REFERENCES scenarios(id),
    content TEXT NOT NULL,
    version INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_briefings_scenario ON briefings(scenario_id);

CREATE TABLE IF NOT EXISTS injected_events (
    id TEXT PRIMARY KEY,
    scenario_id TEXT NOT NULL REFERENCES scenarios(id),
    result_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    content TEXT NOT NULL,
    target_agents TEXT NOT NULL,
    injected_at_round INTEGER,
    status TEXT DEFAULT 'pending',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_injected_events_scenario ON injected_events(scenario_id);
CREATE INDEX IF NOT EXISTS idx_injected_events_scenario_status ON injected_events(scenario_id, status);

CREATE INDEX IF NOT EXISTS idx_simulation_results_scenario ON simulation_results(scenario_id);
CREATE INDEX IF NOT EXISTS idx_seeds_scenario ON seeds(scenario_id);
CREATE INDEX IF NOT EXISTS idx_scenarios_status ON scenarios(status);
CREATE INDEX IF NOT EXISTS idx_decision_points_scenario_status ON decision_points(scenario_id, status);
CREATE INDEX IF NOT EXISTS idx_decision_points_scenario_type_status ON decision_points(scenario_id, type, status);
CREATE INDEX IF NOT EXISTS idx_action_log_scenario_type ON action_log(scenario_id, action_type);

CREATE TABLE IF NOT EXISTS osint_metrics_hourly (
    id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    bucket_hour TEXT NOT NULL,
    region_name TEXT,
    count INTEGER NOT NULL,
    country_breakdown TEXT,
    metadata TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_osint_metrics_source_hour ON osint_metrics_hourly(source_type, bucket_hour);
CREATE INDEX IF NOT EXISTS idx_osint_metrics_region ON osint_metrics_hourly(region_name, bucket_hour);

CREATE TABLE IF NOT EXISTS osint_snapshots (
    id TEXT PRIMARY KEY,
    snapshot_at TEXT NOT NULL,
    region_bbox TEXT,
    asset_counts TEXT NOT NULL,
    tension_indicators TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_osint_snapshots_time ON osint_snapshots(snapshot_at);

CREATE INDEX IF NOT EXISTS idx_obs_source_time ON observations(source_type, source_id, observed_at);
CREATE INDEX IF NOT EXISTS idx_obs_time_range ON observations(observed_at);

CREATE TABLE IF NOT EXISTS whatif_branches (
    id TEXT PRIMARY KEY,
    scenario_id TEXT NOT NULL REFERENCES scenarios(id),
    parent_result_id TEXT NOT NULL,
    branch_result_id TEXT,
    branch_point_round INTEGER,
    modification TEXT NOT NULL,
    execution_mode TEXT DEFAULT 'full_replay',
    world_model_strategy TEXT DEFAULT 'regenerate',
    status TEXT DEFAULT 'pending',
    comparison_data TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_whatif_branches_scenario ON whatif_branches(scenario_id);
CREATE INDEX IF NOT EXISTS idx_whatif_branches_status ON whatif_branches(status);

CREATE TABLE IF NOT EXISTS causal_models (
    id TEXT PRIMARY KEY,
    scenario_id TEXT,
    model_type TEXT NOT NULL,
    dag_json TEXT NOT NULL,
    variables TEXT NOT NULL,
    fit_metadata TEXT,
    status TEXT DEFAULT 'active',
    created_at TEXT NOT NULL,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_causal_models_scenario ON causal_models(scenario_id);
CREATE INDEX IF NOT EXISTS idx_causal_models_type ON causal_models(model_type);

CREATE TABLE IF NOT EXISTS causal_observations (
    id SERIAL PRIMARY KEY,
    scenario_id TEXT NOT NULL,
    result_id TEXT NOT NULL,
    round_num INTEGER NOT NULL,
    variables JSONB NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_causal_obs_scenario ON causal_observations(scenario_id);
CREATE INDEX IF NOT EXISTS idx_causal_obs_result ON causal_observations(result_id);

CREATE TABLE IF NOT EXISTS geopolitics_snapshots (
    id TEXT PRIMARY KEY,
    scenario_id TEXT NOT NULL REFERENCES scenarios(id),
    result_id TEXT NOT NULL,
    round_number INTEGER NOT NULL,
    engine_state TEXT NOT NULL,
    pending_decision_point_id TEXT,
    geopolitics_mode TEXT NOT NULL,
    player_actor_id TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_geo_snap_scenario ON geopolitics_snapshots(scenario_id);
CREATE INDEX IF NOT EXISTS idx_geo_snap_result ON geopolitics_snapshots(result_id);
"""


def get_pool() -> asyncpg.Pool:
    assert _pool is not None, "Database not initialized — call init_db() first"
    return _pool


async def get_db():
    """FastAPI dependency — yields an asyncpg connection from the pool."""
    pool = get_pool()
    async with pool.acquire() as conn:
        yield conn


async def get_db_tx():
    """FastAPI dependency — yields a connection with an active transaction.

    Use for endpoints performing multiple writes across tables.
    All queries succeed together or roll back together.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            yield conn


async def init_db() -> None:
    global _pool
    pool = await asyncpg.create_pool(settings.database_url, min_size=2, max_size=10)
    _pool = pool
    async with pool.acquire() as conn:
        # Keep inline schema execution as a safety net during Alembic adoption.
        # Production deployments should run Alembic migrations before app startup.
        for statement in SCHEMA.strip().split(";"):
            stmt = statement.strip()
            if stmt:
                await conn.execute(stmt + ";")


async def close_db() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
