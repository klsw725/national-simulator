from __future__ import annotations

import asyncpg

from app.config import settings

_pool: asyncpg.Pool | None = None

SCHEMA = """\
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
    payload TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_stix_objects_type ON stix_objects(object_type);
CREATE INDEX IF NOT EXISTS idx_stix_objects_stix_id ON stix_objects(stix_id);
CREATE INDEX IF NOT EXISTS idx_stix_objects_branch ON stix_objects(branch_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_scenario ON scenario_snapshots(scenario_id);
CREATE INDEX IF NOT EXISTS idx_action_log_scenario ON action_log(scenario_id);
CREATE INDEX IF NOT EXISTS idx_action_log_type ON action_log(action_type);
CREATE INDEX IF NOT EXISTS idx_action_log_created ON action_log(created_at);
"""


def get_pool() -> asyncpg.Pool:
    assert _pool is not None, "Database not initialized — call init_db() first"
    return _pool


async def get_db():
    """FastAPI dependency — yields an asyncpg connection from the pool."""
    pool = get_pool()
    async with pool.acquire() as conn:
        yield conn


async def init_db() -> None:
    global _pool
    pool = await asyncpg.create_pool(settings.database_url, min_size=2, max_size=10)
    _pool = pool
    async with pool.acquire() as conn:
        for statement in SCHEMA.strip().split(";"):
            stmt = statement.strip()
            if stmt:
                await conn.execute(stmt + ";")


async def close_db() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
