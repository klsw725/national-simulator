"""Entity resolver — runs matching on observations and stores candidates.

Follows Gotham pattern: observations are never modified (non-destructive).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from app.database import get_pool
from app.resolution.matcher import MatchCandidate, Matcher

AUTO_RESOLVE_THRESHOLD = 0.85


class Resolver:
    def __init__(self) -> None:
        self._matcher = Matcher()

    async def resolve_observation(
        self,
        observation_id: str,
        source_type: str,
        source_id: str,
        raw_data: str,
    ) -> list[dict[str, Any]]:
        """Run matching for a single observation and store candidates.

        Returns the list of stored candidate dicts.
        """
        candidates = await self._matcher.find_candidates(source_type, source_id, raw_data)

        stored: list[dict[str, Any]] = []
        for candidate in candidates:
            record = await self._store_candidate(observation_id, candidate)
            stored.append(record)

        return stored

    async def resolve_batch(
        self,
        observations: list[dict[str, Any]],
    ) -> dict[str, list[dict[str, Any]]]:
        """Run matching for multiple observations.

        Each observation dict must have: id, source_type, source_id, raw_data.
        Returns {observation_id: [candidates]}.
        """
        results: dict[str, list[dict[str, Any]]] = {}
        for obs in observations:
            candidates = await self.resolve_observation(
                observation_id=obs["id"],
                source_type=obs["source_type"],
                source_id=obs["source_id"],
                raw_data=obs["raw_data"],
            )
            results[obs["id"]] = candidates
        return results

    async def get_candidates(
        self,
        observation_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Query stored candidates with optional filters."""
        conditions: list[str] = []
        params: list[Any] = []
        idx = 1

        if observation_id:
            conditions.append(f"observation_id = ${idx}")
            params.append(observation_id)
            idx += 1
        if status:
            conditions.append(f"status = ${idx}")
            params.append(status)
            idx += 1

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = (
            f"SELECT * FROM resolution_candidates {where} "
            f"ORDER BY match_score DESC LIMIT ${idx} OFFSET ${idx + 1}"
        )
        params.extend([limit, offset])

        pool = get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)

        return [_candidate_row_to_dict(row) for row in rows]

    async def get_decisions(
        self,
        observation_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Query resolution decisions."""
        if observation_id:
            sql = "SELECT * FROM resolution_decisions WHERE observation_id = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3"
            params: list[Any] = [observation_id, limit, offset]
        else:
            sql = "SELECT * FROM resolution_decisions ORDER BY created_at DESC LIMIT $1 OFFSET $2"
            params = [limit, offset]

        pool = get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)

        return [_decision_row_to_dict(row) for row in rows]

    # ------------------------------------------------------------------
    # M3: Auto-resolve — threshold-based automatic resolution
    # ------------------------------------------------------------------

    async def auto_resolve(
        self,
        observation_id: str,
        source_type: str,
        source_id: str,
        raw_data: str,
    ) -> dict[str, Any]:
        """Run matching, store candidates, and auto-resolve high-confidence ones.

        Returns summary: {candidates: [...], auto_resolved: [...], pending_review: [...]}.
        """
        candidates = await self.resolve_observation(
            observation_id, source_type, source_id, raw_data,
        )

        auto_resolved: list[dict[str, Any]] = []
        pending_review: list[dict[str, Any]] = []

        for cand in candidates:
            if cand["match_score"] >= AUTO_RESOLVE_THRESHOLD:
                decision = await self._auto_accept(cand)
                auto_resolved.append(decision)
            else:
                pending_review.append(cand)

        return {
            "observation_id": observation_id,
            "total_candidates": len(candidates),
            "auto_resolved": auto_resolved,
            "pending_review": pending_review,
        }

    # ------------------------------------------------------------------
    # M4: Accept / Reject / Merge — manual review operations
    # ------------------------------------------------------------------

    async def accept_candidate(
        self,
        candidate_id: str,
        decided_by: str,
    ) -> dict[str, Any]:
        """Accept a candidate — mark as accepted and record decision."""
        cand = await self._get_candidate_by_id(candidate_id)
        if not cand:
            raise ValueError(f"Candidate {candidate_id} not found")
        if cand["status"] != "pending":
            raise ValueError(f"Candidate {candidate_id} is not pending (status={cand['status']})")

        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE resolution_candidates SET status = 'accepted' WHERE id = $1",
                candidate_id,
            )

        decision = await self._record_decision(
            observation_id=cand["observation_id"],
            resolved_stix_id=cand["candidate_stix_id"],
            decision_type="manual_merge",
            decided_by=decided_by,
            confidence=cand["match_score"],
            reason=f"Manually accepted candidate {candidate_id}",
        )
        return decision

    async def reject_candidate(
        self,
        candidate_id: str,
        decided_by: str,
    ) -> dict[str, Any]:
        """Reject a candidate — mark as rejected and record decision."""
        cand = await self._get_candidate_by_id(candidate_id)
        if not cand:
            raise ValueError(f"Candidate {candidate_id} not found")
        if cand["status"] != "pending":
            raise ValueError(f"Candidate {candidate_id} is not pending (status={cand['status']})")

        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE resolution_candidates SET status = 'rejected' WHERE id = $1",
                candidate_id,
            )

        decision = await self._record_decision(
            observation_id=cand["observation_id"],
            resolved_stix_id=cand["candidate_stix_id"],
            decision_type="manual_reject",
            decided_by=decided_by,
            confidence=cand["match_score"],
            reason=f"Manually rejected candidate {candidate_id}",
        )
        return decision

    async def merge_entities(
        self,
        observation_id: str,
        target_stix_id: str,
        decided_by: str,
    ) -> dict[str, Any]:
        """Manually merge an observation to a stix_object (no candidate required)."""
        decision = await self._record_decision(
            observation_id=observation_id,
            resolved_stix_id=target_stix_id,
            decision_type="manual_merge",
            decided_by=decided_by,
            confidence=1.0,
            reason=f"Direct merge by {decided_by}",
        )
        return decision

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _auto_accept(self, candidate: dict[str, Any]) -> dict[str, Any]:
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE resolution_candidates SET status = 'accepted' WHERE id = $1",
                candidate["id"],
            )

        return await self._record_decision(
            observation_id=candidate["observation_id"],
            resolved_stix_id=candidate["candidate_stix_id"],
            decision_type="auto",
            decided_by="system",
            confidence=candidate["match_score"],
            reason=f"Auto-resolved: {candidate['match_strategy']} score={candidate['match_score']}",
        )

    async def _record_decision(
        self,
        observation_id: str,
        resolved_stix_id: str,
        decision_type: str,
        decided_by: str,
        confidence: float,
        reason: str,
    ) -> dict[str, Any]:
        dec_id = f"rd_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()

        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO resolution_decisions
                   (id, observation_id, resolved_stix_id, decision_type,
                    decided_by, confidence, reason, created_at)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
                dec_id, observation_id, resolved_stix_id,
                decision_type, decided_by, confidence, reason, now,
            )

        return {
            "id": dec_id,
            "observation_id": observation_id,
            "resolved_stix_id": resolved_stix_id,
            "decision_type": decision_type,
            "decided_by": decided_by,
            "confidence": confidence,
            "reason": reason,
            "created_at": now,
        }

    async def _get_candidate_by_id(self, candidate_id: str) -> dict[str, Any] | None:
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM resolution_candidates WHERE id = $1", candidate_id,
            )
        return _candidate_row_to_dict(row) if row else None

    # ------------------------------------------------------------------
    # Original internal (M2)
    # ------------------------------------------------------------------

    async def _store_candidate(
        self,
        observation_id: str,
        candidate: MatchCandidate,
    ) -> dict[str, Any]:
        cand_id = f"rc_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()

        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO resolution_candidates
                   (id, observation_id, candidate_stix_id, match_score,
                    match_strategy, match_reason, status, created_at)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
                cand_id,
                observation_id,
                candidate.candidate_stix_id,
                candidate.match_score,
                candidate.match_strategy,
                json.dumps(candidate.match_reason, ensure_ascii=False),
                "pending",
                now,
            )

        return {
            "id": cand_id,
            "observation_id": observation_id,
            "candidate_stix_id": candidate.candidate_stix_id,
            "match_score": candidate.match_score,
            "match_strategy": candidate.match_strategy,
            "match_reason": candidate.match_reason,
            "status": "pending",
            "created_at": now,
        }


def _candidate_row_to_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "observation_id": row["observation_id"],
        "candidate_stix_id": row["candidate_stix_id"],
        "match_score": row["match_score"],
        "match_strategy": row["match_strategy"],
        "match_reason": json.loads(row["match_reason"]) if row["match_reason"] else None,
        "status": row["status"],
        "created_at": row["created_at"],
    }


def _decision_row_to_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "observation_id": row["observation_id"],
        "resolved_stix_id": row["resolved_stix_id"],
        "decision_type": row["decision_type"],
        "decided_by": row["decided_by"],
        "confidence": row["confidence"],
        "reason": row["reason"],
        "created_at": row["created_at"],
    }
