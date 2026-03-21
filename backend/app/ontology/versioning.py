from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from app.database import get_pool

# ---------------------------------------------------------------------------
# Breaking vs non-breaking change classification
# ---------------------------------------------------------------------------
_BREAKING_CHANGES = {"field_removed", "field_type_changed", "required_added", "sdo_type_removed"}
_NON_BREAKING_CHANGES = {"field_added_optional", "sdo_type_added", "description_changed"}


def _schema_hash(schema_json: dict[str, Any]) -> str:
    canonical = json.dumps(schema_json, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


class OntologyVersioning:
    """Ontology schema version management — register, diff, compatibility check."""

    async def register(
        self,
        version: str,
        schema_json: dict[str, Any],
        change_summary: str = "",
        created_by: str = "system",
    ) -> dict[str, Any]:
        """Register a new ontology version. Skips if schema_hash unchanged."""
        schema_hash = _schema_hash(schema_json)

        existing = await self._get_by_hash(schema_hash)
        if existing:
            return {**existing, "skipped": True, "reason": "identical schema already registered"}

        is_breaking = False
        latest = await self.get_latest()
        if latest:
            diff = self.compute_diff(
                json.loads(latest["schema_json"]) if isinstance(latest["schema_json"], str) else latest["schema_json"],
                schema_json,
            )
            is_breaking = any(c["type"] in _BREAKING_CHANGES for c in diff)

        row_id = f"ov_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()

        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO ontology_versions
                   (id, version, schema_hash, schema_json, change_summary, is_breaking, created_by, created_at)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
                row_id, version, schema_hash,
                json.dumps(schema_json, ensure_ascii=False),
                change_summary, is_breaking, created_by, now,
            )

        return {
            "id": row_id,
            "version": version,
            "schema_hash": schema_hash,
            "is_breaking": is_breaking,
            "created_at": now,
            "skipped": False,
        }

    async def list_versions(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        pool = get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM ontology_versions ORDER BY created_at DESC LIMIT $1 OFFSET $2",
                limit, offset,
            )
        return [_row_to_dict(row) for row in rows]

    async def get_version(self, version: str) -> dict[str, Any] | None:
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM ontology_versions WHERE version = $1", version,
            )
        return _row_to_dict(row) if row else None

    async def get_latest(self) -> dict[str, Any] | None:
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM ontology_versions ORDER BY created_at DESC LIMIT 1",
            )
        return _row_to_dict(row) if row else None

    async def diff(self, from_version: str, to_version: str) -> dict[str, Any]:
        """Compute diff between two registered versions."""
        v_from = await self.get_version(from_version)
        v_to = await self.get_version(to_version)
        if not v_from:
            raise ValueError(f"Version '{from_version}' not found")
        if not v_to:
            raise ValueError(f"Version '{to_version}' not found")

        schema_from = json.loads(v_from["schema_json"]) if isinstance(v_from["schema_json"], str) else v_from["schema_json"]
        schema_to = json.loads(v_to["schema_json"]) if isinstance(v_to["schema_json"], str) else v_to["schema_json"]

        changes = self.compute_diff(schema_from, schema_to)
        has_breaking = any(c["type"] in _BREAKING_CHANGES for c in changes)

        return {
            "from_version": from_version,
            "to_version": to_version,
            "changes": changes,
            "is_breaking": has_breaking,
            "total_changes": len(changes),
        }

    async def validate(self, schema_json: dict[str, Any]) -> dict[str, Any]:
        """Check compatibility of a new schema against the latest version."""
        latest = await self.get_latest()
        if not latest:
            return {"compatible": True, "reason": "no previous version", "changes": []}

        latest_schema = json.loads(latest["schema_json"]) if isinstance(latest["schema_json"], str) else latest["schema_json"]
        changes = self.compute_diff(latest_schema, schema_json)
        breaking = [c for c in changes if c["type"] in _BREAKING_CHANGES]

        return {
            "compatible": len(breaking) == 0,
            "latest_version": latest["version"],
            "total_changes": len(changes),
            "breaking_changes": breaking,
            "non_breaking_changes": [c for c in changes if c["type"] in _NON_BREAKING_CHANGES],
        }

    # ------------------------------------------------------------------
    # Diff computation (pure function, no DB)
    # ------------------------------------------------------------------

    @staticmethod
    def compute_diff(
        old_schema: dict[str, Any],
        new_schema: dict[str, Any],
    ) -> list[dict[str, str]]:
        changes: list[dict[str, str]] = []

        old_types = {t["name"]: t for t in old_schema.get("entity_types", [])}
        new_types = {t["name"]: t for t in new_schema.get("entity_types", [])}

        for name in old_types:
            if name not in new_types:
                changes.append({"type": "sdo_type_removed", "name": name})
        for name in new_types:
            if name not in old_types:
                changes.append({"type": "sdo_type_added", "name": name})

        old_edges = {e["name"]: e for e in old_schema.get("edge_types", [])}
        new_edges = {e["name"]: e for e in new_schema.get("edge_types", [])}

        for name in old_edges:
            if name not in new_edges:
                changes.append({"type": "field_removed", "name": f"edge:{name}"})
        for name in new_edges:
            if name not in old_edges:
                changes.append({"type": "field_added_optional", "name": f"edge:{name}"})

        for name in old_types:
            if name in new_types:
                old_desc = old_types[name].get("description", "")
                new_desc = new_types[name].get("description", "")
                if old_desc != new_desc:
                    changes.append({"type": "description_changed", "name": name})

        return changes

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _get_by_hash(self, schema_hash: str) -> dict[str, Any] | None:
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM ontology_versions WHERE schema_hash = $1", schema_hash,
            )
        return _row_to_dict(row) if row else None


def _row_to_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "version": row["version"],
        "schema_hash": row["schema_hash"],
        "schema_json": row["schema_json"],
        "change_summary": row["change_summary"],
        "is_breaking": row["is_breaking"],
        "created_by": row["created_by"],
        "created_at": row["created_at"],
    }
