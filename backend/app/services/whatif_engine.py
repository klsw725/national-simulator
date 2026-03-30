from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from app.clients.mirofish import MiroFishClient
from app.database import get_pool
from app.models.interactive import WhatIfComparison, WhatIfCreateRequest
from app.models.scenario import SimulationParams
from app.services.simulation_orchestrator import SimulationOrchestrator

logger = logging.getLogger(__name__)

WHATIF_SEED_SEPARATOR = "\n\n--- What-If 가설 ---\n"
MAX_CONCURRENT_BRANCHES = 3

TENSION_KEYWORDS_TYPE = frozenset(
    ("military", "threat", "attack", "sanction", "blockade"),
)
TENSION_KEYWORDS_CONTENT = (
    "전쟁", "공격", "위협", "제재", "봉쇄",
    "war", "attack", "threat", "sanction",
)


class WhatIfEngine:
    def __init__(self, mf_client: MiroFishClient, sb_client=None):
        self.orchestrator = SimulationOrchestrator(mf_client, sb_client)

    async def create_branch(
        self,
        scenario_id: str,
        request: WhatIfCreateRequest,
    ) -> dict[str, Any]:
        pool = get_pool()
        async with pool.acquire() as conn:
            running = await conn.fetchval(
                "SELECT COUNT(*) FROM whatif_branches WHERE scenario_id = $1 AND status IN ('pending', 'running')",
                scenario_id,
            )
            if running >= MAX_CONCURRENT_BRANCHES:
                raise ValueError(f"Maximum {MAX_CONCURRENT_BRANCHES} concurrent branches per scenario")

            scenario = await conn.fetchrow(
                "SELECT id, max_rounds, simulation_params FROM scenarios WHERE id = $1",
                scenario_id,
            )
            if not scenario:
                raise ValueError("Scenario not found")

            parent_result = await conn.fetchrow(
                "SELECT id, status FROM simulation_results WHERE scenario_id = $1 ORDER BY created_at DESC LIMIT 1",
                scenario_id,
            )
            if not parent_result:
                raise ValueError("No simulation result found for this scenario")

            seed_row = await conn.fetchrow(
                "SELECT text FROM seeds WHERE scenario_id = $1 ORDER BY created_at DESC LIMIT 1",
                scenario_id,
            )
            original_seed = seed_row["text"] if seed_row else ""

            augmented_seed = original_seed + WHATIF_SEED_SEPARATOR + request.modification

            max_rounds = request.max_rounds_override or scenario["max_rounds"]
            sim_params_raw = scenario["simulation_params"]
            sim_params = SimulationParams.model_validate_json(sim_params_raw or "{}")

            branch_id = f"wib_{uuid.uuid4().hex[:12]}"
            result_id = f"res_{uuid.uuid4().hex[:12]}"
            now = datetime.now(timezone.utc).isoformat()

            await conn.execute(
                """INSERT INTO simulation_results
                   (id, scenario_id, status, pipeline_mode, created_at)
                   VALUES ($1, $2, 'pending', 'auto', $3)""",
                result_id, scenario_id, now,
            )

            await conn.execute(
                """INSERT INTO whatif_branches
                   (id, scenario_id, parent_result_id, branch_result_id,
                    branch_point_round, modification, execution_mode,
                    world_model_strategy, status, created_at)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'running', $9)""",
                branch_id,
                scenario_id,
                parent_result["id"],
                result_id,
                request.branch_point_round,
                request.modification,
                request.execution_mode,
                "regenerate",
                now,
            )

        return {
            "branch_id": branch_id,
            "result_id": result_id,
            "augmented_seed": augmented_seed,
            "max_rounds": max_rounds,
            "simulation_params": sim_params,
        }

    async def run_branch_pipeline(
        self,
        scenario_id: str,
        branch_id: str,
        result_id: str,
        augmented_seed: str,
        max_rounds: int,
        simulation_params: SimulationParams | None = None,
    ) -> None:
        try:
            await self.orchestrator.run_pipeline(
                scenario_id,
                result_id,
                augmented_seed,
                max_rounds,
                simulation_params=simulation_params,
            )
            pool = get_pool()
            now = datetime.now(timezone.utc).isoformat()
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE whatif_branches SET status = 'completed', completed_at = $1 WHERE id = $2",
                    now, branch_id,
                )
            logger.info("[%s] What-If branch %s completed", scenario_id, branch_id)
        except Exception as exc:
            logger.exception("[%s] What-If branch %s failed", scenario_id, branch_id)
            pool = get_pool()
            now = datetime.now(timezone.utc).isoformat()
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE whatif_branches SET status = 'failed', completed_at = $1 WHERE id = $2",
                    now, branch_id,
                )
            raise

    async def compare(self, branch_id: str) -> WhatIfComparison:
        pool = get_pool()
        async with pool.acquire() as conn:
            branch = await conn.fetchrow(
                "SELECT * FROM whatif_branches WHERE id = $1", branch_id,
            )
            if not branch:
                raise ValueError("Branch not found")
            if branch["status"] != "completed":
                raise ValueError(f"Branch not completed, status: {branch['status']}")

            parent_result = await conn.fetchrow(
                "SELECT results FROM simulation_results WHERE id = $1",
                branch["parent_result_id"],
            )
            branch_result = await conn.fetchrow(
                "SELECT results FROM simulation_results WHERE id = $1",
                branch["branch_result_id"],
            )

            parent_actions = _parse_actions(parent_result["results"] if parent_result else None)
            branch_actions = _parse_actions(branch_result["results"] if branch_result else None)

            scenario = await conn.fetchrow(
                "SELECT max_rounds FROM scenarios WHERE id = $1",
                branch["scenario_id"],
            )
            max_rounds = scenario["max_rounds"] if scenario else 10

            geo_parent = await conn.fetchval(
                "SELECT COUNT(*) FROM geopolitics_events WHERE scenario_id = $1 AND simulation_result_id = $2",
                branch["scenario_id"], branch["parent_result_id"],
            )
            geo_branch = await conn.fetchval(
                "SELECT COUNT(*) FROM geopolitics_events WHERE scenario_id = $1 AND simulation_result_id = $2",
                branch["scenario_id"], branch["branch_result_id"],
            )

        metrics = compute_maxs_metrics(parent_actions, branch_actions, max_rounds)
        actor_diff = _compute_actor_diff(parent_actions, branch_actions)
        causal_attribution = None
        try:
            from app.services.causal_reasoner import CausalReasoner

            reasoner = CausalReasoner()
            if reasoner.is_fitted("domain"):
                attr_result = reasoner.attribute("domain", "tension_ratio")
                causal_attribution = {
                    "tension_advantage_explained": attr_result.get("attributions", {}),
                    "confidence": "medium" if attr_result.get("total_explained", 0) > 0.5 else "low",
                    "method": attr_result.get("method", "intervention_range"),
                }
        except Exception as exc:
            logger.debug("Causal attribution skipped: %s", exc)

        comparison = WhatIfComparison(
            branch_id=branch_id,
            tension_advantage=metrics["tension_advantage"],
            tension_curves=metrics["tension_curves"],
            step_variance=metrics["step_variance"],
            slope_variance=metrics["slope_variance"],
            actor_diff=actor_diff,
            action_count_delta=len(branch_actions) - len(parent_actions),
            geopolitics_delta=(geo_branch or 0) - (geo_parent or 0),
            causal_attribution=causal_attribution,
        )

        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE whatif_branches SET comparison_data = $1 WHERE id = $2",
                json.dumps(comparison.model_dump(), ensure_ascii=False),
                branch_id,
            )

        return comparison


def _parse_actions(raw: str | None) -> list[dict]:
    if not raw:
        return []
    parsed = json.loads(raw)
    if isinstance(parsed, dict) and "actions" in parsed:
        return parsed["actions"]
    if isinstance(parsed, list):
        return parsed
    return []


def _compute_round_tension(actions: list[dict], round_num: int) -> float:
    round_actions = [
        a for a in actions
        if a.get("round") == round_num or a.get("round_num") == round_num
    ]
    if not round_actions:
        return 0.0

    tension_signals = 0
    total = 0
    for action in round_actions:
        content = (action.get("content") or action.get("text") or "").lower()
        action_type = (action.get("action_type") or action.get("type") or "").lower()
        total += 1
        if action_type in TENSION_KEYWORDS_TYPE:
            tension_signals += 1
        elif any(kw in content for kw in TENSION_KEYWORDS_CONTENT):
            tension_signals += 1

    return round(tension_signals / total, 4) if total else 0.0


def _variance(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return round(sum((v - mean) ** 2 for v in values) / len(values), 6)


def _slope_variance(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    diffs = [values[i + 1] - values[i] for i in range(len(values) - 1)]
    return _variance(diffs)


def compute_maxs_metrics(
    original_actions: list[dict],
    branch_actions: list[dict],
    max_rounds: int,
) -> dict[str, Any]:
    orig_tensions = [_compute_round_tension(original_actions, r) for r in range(1, max_rounds + 1)]
    branch_tensions = [_compute_round_tension(branch_actions, r) for r in range(1, max_rounds + 1)]

    orig_final = orig_tensions[-1] if orig_tensions else 0.0
    branch_final = branch_tensions[-1] if branch_tensions else 0.0

    return {
        "tension_advantage": round(branch_final - orig_final, 4),
        "tension_curves": {"original": orig_tensions, "branch": branch_tensions},
        "step_variance": {
            "original": _variance(orig_tensions),
            "branch": _variance(branch_tensions),
        },
        "slope_variance": {
            "original": _slope_variance(orig_tensions),
            "branch": _slope_variance(branch_tensions),
        },
    }


def _compute_actor_diff(original_actions: list[dict], branch_actions: list[dict]) -> dict:
    def _extract_actors(actions: list[dict]) -> set[str]:
        actors: set[str] = set()
        for a in actions:
            actor = a.get("agent_name") or a.get("actor") or a.get("author") or ""
            if actor:
                actors.add(actor)
        return actors

    orig_actors = _extract_actors(original_actions)
    branch_actors = _extract_actors(branch_actions)

    return {
        "only_original": sorted(orig_actors - branch_actors),
        "only_branch": sorted(branch_actors - orig_actors),
        "common": sorted(orig_actors & branch_actors),
    }
