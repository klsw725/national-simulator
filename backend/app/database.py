from pathlib import Path

import aiosqlite

from app.config import settings

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
"""


def _db_path() -> Path:
    return Path(settings.database_path)


async def get_db():
    """FastAPI dependency — yields an aiosqlite connection."""
    db_path = _db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(str(db_path))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    try:
        yield db
    finally:
        await db.close()


async def init_db():
    """Create tables on startup."""
    db_path = _db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(str(db_path))
    try:
        await db.executescript(SCHEMA)
        await db.commit()
    finally:
        await db.close()
