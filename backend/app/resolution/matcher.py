"""Entity resolution matching engine.

Strategies (priority order):
  1. Exact match  — MMSI, IMO, ICAO24, NORAD ID  (score: 1.0)
  2. Fuzzy match  — name similarity                (score: 0.6–0.9)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

from app.database import get_pool

# ---------------------------------------------------------------------------
# Match result container
# ---------------------------------------------------------------------------

@dataclass
class MatchCandidate:
    candidate_stix_id: str
    match_score: float
    match_strategy: str
    match_reason: dict[str, Any]


# ---------------------------------------------------------------------------
# Identifier extraction from raw observation data
# ---------------------------------------------------------------------------

# Map source_type → list of (raw_data field, stix_json field, strategy name)
_EXACT_ID_FIELDS: dict[str, list[tuple[str, str, str]]] = {
    "ship": [
        ("mmsi", "mmsi", "exact_mmsi"),
        ("imo", "imo", "exact_imo"),
    ],
    "flight": [
        ("icao24", "icao24", "exact_icao24"),
    ],
    "satellite": [
        ("norad_id", "norad_id", "exact_norad"),
    ],
}

# Map source_type → stix object_type for fuzzy search scope
_SOURCE_TO_STIX_TYPE: dict[str, str] = {
    "ship": "x-vessel",
    "flight": "x-aircraft",
    "satellite": "x-satellite",
}


def _parse_raw(raw_data: str) -> dict[str, Any]:
    try:
        return json.loads(raw_data)
    except (json.JSONDecodeError, TypeError):
        return {}


def _name_similarity(a: str, b: str) -> float:
    """Normalized name similarity using SequenceMatcher (0.0–1.0)."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


# ---------------------------------------------------------------------------
# Matching engine
# ---------------------------------------------------------------------------

class Matcher:
    """Find candidate stix_objects for a given observation."""

    async def find_candidates(
        self,
        source_type: str,
        source_id: str,
        raw_data: str,
    ) -> list[MatchCandidate]:
        """Run all matching strategies and return sorted candidates."""
        candidates: list[MatchCandidate] = []

        parsed = _parse_raw(raw_data)

        # Strategy 1: Exact identifier match
        exact = await self._exact_match(source_type, source_id, parsed)
        candidates.extend(exact)

        # Strategy 2: Fuzzy name match (only if no perfect exact match)
        has_perfect = any(c.match_score >= 1.0 for c in candidates)
        if not has_perfect:
            fuzzy = await self._fuzzy_name_match(source_type, parsed)
            # Deduplicate — skip stix_ids already found by exact match
            existing_ids = {c.candidate_stix_id for c in candidates}
            candidates.extend(c for c in fuzzy if c.candidate_stix_id not in existing_ids)

        # Sort by score descending
        candidates.sort(key=lambda c: c.match_score, reverse=True)
        return candidates

    # ------------------------------------------------------------------
    # Strategy 1: Exact identifier match
    # ------------------------------------------------------------------
    async def _exact_match(
        self,
        source_type: str,
        source_id: str,
        parsed: dict[str, Any],
    ) -> list[MatchCandidate]:
        id_fields = _EXACT_ID_FIELDS.get(source_type, [])
        if not id_fields:
            return []

        candidates: list[MatchCandidate] = []
        pool = get_pool()

        async with pool.acquire() as conn:
            stix_type = _SOURCE_TO_STIX_TYPE.get(source_type)
            if not stix_type:
                return []

            rows = await conn.fetch(
                "SELECT stix_id, stix_json FROM stix_objects WHERE object_type = $1",
                stix_type,
            )

        for row in rows:
            stix_id = row["stix_id"]
            try:
                stix_data = json.loads(row["stix_json"])
            except (json.JSONDecodeError, TypeError):
                continue

            for raw_field, stix_field, strategy in id_fields:
                obs_val = parsed.get(raw_field) or source_id if raw_field == _primary_id_field(source_type) else parsed.get(raw_field)
                stix_val = stix_data.get(stix_field)
                if obs_val and stix_val and str(obs_val).strip() == str(stix_val).strip():
                    candidates.append(MatchCandidate(
                        candidate_stix_id=stix_id,
                        match_score=1.0,
                        match_strategy=strategy,
                        match_reason={"field": raw_field, "value": str(obs_val)},
                    ))
                    break  # One exact match per stix_object is enough

        return candidates

    # ------------------------------------------------------------------
    # Strategy 2: Fuzzy name match
    # ------------------------------------------------------------------
    async def _fuzzy_name_match(
        self,
        source_type: str,
        parsed: dict[str, Any],
    ) -> list[MatchCandidate]:
        obs_name = parsed.get("name") or parsed.get("callsign") or ""
        if not obs_name or len(obs_name) < 2:
            return []

        stix_type = _SOURCE_TO_STIX_TYPE.get(source_type)
        if not stix_type:
            return []

        pool = get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT stix_id, stix_json FROM stix_objects WHERE object_type = $1",
                stix_type,
            )

        candidates: list[MatchCandidate] = []
        for row in rows:
            stix_id = row["stix_id"]
            try:
                stix_data = json.loads(row["stix_json"])
            except (json.JSONDecodeError, TypeError):
                continue

            stix_name = stix_data.get("name", "")
            score = _name_similarity(obs_name, stix_name)

            if score >= 0.6:
                candidates.append(MatchCandidate(
                    candidate_stix_id=stix_id,
                    match_score=round(score, 3),
                    match_strategy="fuzzy_name",
                    match_reason={
                        "observation_name": obs_name,
                        "stix_name": stix_name,
                        "similarity": round(score, 3),
                    },
                ))

        return candidates


def _primary_id_field(source_type: str) -> str:
    """Return the primary identifier field name for source_id mapping."""
    return {"ship": "mmsi", "flight": "icao24", "satellite": "norad_id"}.get(source_type, "")
