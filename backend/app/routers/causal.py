from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
import networkx as nx
from pydantic import BaseModel

from app.causal.domain_dag import build_domain_dag, dag_from_serializable, dag_to_serializable
from app.causal.models import (
    AttributionRequest,
    AttributionResult,
    CausalExtractRequest,
    CausalExtractResult,
    CausalFitRequest,
    CausalNarrateRequest,
    CausalNarrateResult,
    CounterfactualRequest,
    CounterfactualResult,
    InterventionRequest,
    InterventionResult,
)
from app.database import get_pool
from app.services.causal_log_collector import CausalLogCollector
from app.services.causal_reasoner import CausalReasoner

router = APIRouter(prefix="/api/causal", tags=["causal"])
_reasoner = CausalReasoner()


class CausalCollectRequest(BaseModel):
    scenario_id: str
    result_id: str


class CausalLearnRequest(BaseModel):
    scenario_id: str
    n_bootstrap: int = 50
    stability_threshold: float = 0.7


@router.get("/domain_dag")
async def get_domain_dag():
    dag = build_domain_dag()
    return {
        "model_type": "domain",
        "dag": dag_to_serializable(dag),
    }


@router.post("/collect")
async def collect_causal_logs(body: CausalCollectRequest):
    collector = CausalLogCollector()
    collected = await collector.collect_from_result(body.scenario_id, body.result_id)
    return {
        "scenario_id": body.scenario_id,
        "result_id": body.result_id,
        "collected": collected,
    }


@router.post("/learn")
async def learn_causal_structure(body: CausalLearnRequest):
    collector = CausalLogCollector()
    df = await collector.build_dataframe(body.scenario_id)
    if df is None:
        raise HTTPException(status_code=400, detail="Not enough causal observations")

    from app.causal.structure_learner import CausalStructureLearner
    learner = CausalStructureLearner()
    domain_dag = build_domain_dag()

    try:
        learned_dag = learner.learn_structure(
            df,
            n_bootstrap=body.n_bootstrap,
            stability_threshold=body.stability_threshold,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    comparison = learner.compare_with_domain(learned_dag, domain_dag)
    merged_dag = learner.merge_dags(domain_dag, learned_dag, domain_priority=True)

    now = datetime.now(timezone.utc).isoformat()
    learned_model_id = f"cmdl_{uuid.uuid4().hex[:12]}"
    merged_model_id = f"cmdl_{uuid.uuid4().hex[:12]}"
    fit_metadata = {
        "n_rows": int(len(df)),
        "n_bootstrap": body.n_bootstrap,
        "stability_threshold": body.stability_threshold,
        "comparison": comparison,
    }

    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO causal_models
               (id, scenario_id, model_type, dag_json, variables, fit_metadata, created_at)
               VALUES ($1, $2, $3, $4, $5, $6, $7)""",
            learned_model_id,
            body.scenario_id,
            "learned",
            json.dumps(dag_to_serializable(learned_dag), ensure_ascii=False),
            json.dumps(sorted([str(col) for col in df.columns]), ensure_ascii=False),
            json.dumps(fit_metadata, ensure_ascii=False),
            now,
        )
        await conn.execute(
            """INSERT INTO causal_models
               (id, scenario_id, model_type, dag_json, variables, fit_metadata, created_at)
               VALUES ($1, $2, $3, $4, $5, $6, $7)""",
            merged_model_id,
            body.scenario_id,
            "merged",
            json.dumps(dag_to_serializable(merged_dag), ensure_ascii=False),
            json.dumps(sorted([str(col) for col in df.columns]), ensure_ascii=False),
            json.dumps(fit_metadata, ensure_ascii=False),
            now,
        )

    return {
        "scenario_id": body.scenario_id,
        "learned_model_id": learned_model_id,
        "merged_model_id": merged_model_id,
        "comparison": comparison,
    }


@router.get("/models")
async def list_causal_models(scenario_id: str | None = None):
    pool = get_pool()
    async with pool.acquire() as conn:
        if scenario_id:
            rows = await conn.fetch(
                """SELECT id, scenario_id, model_type, fit_metadata, status, created_at, updated_at
                   FROM causal_models
                   WHERE scenario_id = $1
                   ORDER BY created_at DESC""",
                scenario_id,
            )
        else:
            rows = await conn.fetch(
                """SELECT id, scenario_id, model_type, fit_metadata, status, created_at, updated_at
                   FROM causal_models
                   ORDER BY created_at DESC""",
            )

    models = []
    for row in rows:
        models.append(
            {
                "id": row["id"],
                "scenario_id": row["scenario_id"],
                "model_type": row["model_type"],
                "fit_metadata": json.loads(row["fit_metadata"]) if row["fit_metadata"] else None,
                "status": row["status"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            },
        )
    return {"count": len(models), "models": models}


@router.get("/models/{model_id}")
async def get_causal_model(model_id: str):
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT id, scenario_id, model_type, dag_json, variables,
                      fit_metadata, status, created_at, updated_at
               FROM causal_models
               WHERE id = $1""",
            model_id,
        )

    if not row:
        raise HTTPException(status_code=404, detail="Causal model not found")

    return {
        "id": row["id"],
        "scenario_id": row["scenario_id"],
        "model_type": row["model_type"],
        "dag": json.loads(row["dag_json"]),
        "variables": json.loads(row["variables"]),
        "fit_metadata": json.loads(row["fit_metadata"]) if row["fit_metadata"] else None,
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


@router.post("/fit")
async def fit_causal_model(body: CausalFitRequest):
    if not body.scenario_id:
        raise HTTPException(status_code=400, detail="scenario_id is required")

    dag = build_domain_dag()
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT dag_json FROM causal_models WHERE id = $1",
            body.model_id,
        )
    if row and row["dag_json"]:
        dag_json = row["dag_json"]
        dag_data = json.loads(dag_json) if isinstance(dag_json, str) else dag_json
        dag = dag_from_serializable(dag_data)

    collector = CausalLogCollector()
    df = await collector.build_dataframe(body.scenario_id, min_results=1)
    if df is None:
        raise HTTPException(
            status_code=400,
            detail="No causal observations. Run a simulation for this scenario first.",
        )

    try:
        result = _reasoner.fit(body.model_id, dag, df)
    except (ImportError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return result


@router.post("/intervene", response_model=InterventionResult)
async def causal_intervene(body: InterventionRequest):
    if not _reasoner.is_fitted(body.model_id):
        raise HTTPException(status_code=400, detail="Model is not fitted")
    try:
        result = _reasoner.intervene(
            model_id=body.model_id,
            interventions=body.interventions,
            target_variables=body.target_variables,
            num_samples=body.num_samples,
        )
    except (ImportError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return InterventionResult(**result)


@router.post("/counterfactual", response_model=CounterfactualResult)
async def causal_counterfactual(body: CounterfactualRequest):
    if not _reasoner.is_fitted(body.model_id):
        raise HTTPException(status_code=400, detail="Model is not fitted")
    try:
        result = _reasoner.counterfactual(
            model_id=body.model_id,
            observed=body.observed,
            interventions=body.interventions,
        )
    except (ImportError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CounterfactualResult(**result)


@router.post("/attribute", response_model=AttributionResult)
async def causal_attribute(body: AttributionRequest):
    if not _reasoner.is_fitted(body.model_id):
        raise HTTPException(status_code=400, detail="Model is not fitted")
    try:
        result = _reasoner.attribute(
            model_id=body.model_id,
            target_variable=body.target_variable,
        )
    except (ImportError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AttributionResult(**result)


@router.post("/extract", response_model=CausalExtractResult)
async def extract_causal_relations(body: CausalExtractRequest):
    from app.services.causal_extractor import CausalExtractor
    extractor = CausalExtractor()

    df = None
    verified = False
    if body.scenario_id:
        collector = CausalLogCollector()
        try:
            df = await collector.build_dataframe(body.scenario_id)
            verified = df is not None and len(df) >= 30
        except Exception:
            df = None
            verified = False

    edges = await extractor.extract_and_validate(body.text, df)
    return CausalExtractResult(edges=edges, verified=verified)


@router.get("/models/{model_id}/paths")
async def get_causal_paths(model_id: str, target: str, max_paths: int = 5):
    dag = build_domain_dag()
    fit_metadata: dict | None = None

    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT dag_json, fit_metadata FROM causal_models WHERE id = $1",
            model_id,
        )

    if row and row["dag_json"]:
        dag_json = row["dag_json"]
        dag_data = json.loads(dag_json) if isinstance(dag_json, str) else dag_json
        dag = dag_from_serializable(dag_data)
    if row and row["fit_metadata"]:
        fit_metadata_raw = row["fit_metadata"]
        fit_metadata = json.loads(fit_metadata_raw) if isinstance(fit_metadata_raw, str) else fit_metadata_raw

    if target not in dag.nodes:
        raise HTTPException(status_code=400, detail="Target variable not in DAG")

    max_paths = max(1, min(50, int(max_paths)))
    paths: list[list[str]] = []
    ancestors = sorted(nx.ancestors(dag, target))

    for source in ancestors:
        if len(paths) >= max_paths:
            break
        try:
            for path in nx.all_simple_paths(dag, source=source, target=target):
                paths.append([str(node) for node in path])
                if len(paths) >= max_paths:
                    break
        except nx.NetworkXNoPath:
            continue

    attributions: dict[str, float] = {}
    if _reasoner.is_fitted(model_id):
        try:
            attribution_result = _reasoner.attribute(model_id=model_id, target_variable=target)
            attributions = {
                str(k): float(v)
                for k, v in attribution_result.get("attributions", {}).items()
            }
        except Exception:
            attributions = {}
    elif isinstance(fit_metadata, dict):
        raw_attr = fit_metadata.get("attributions")
        if isinstance(raw_attr, dict):
            attributions = {str(k): float(v) for k, v in raw_attr.items()}

    return {
        "model_id": model_id,
        "target": target,
        "paths": paths,
        "attributions": attributions,
    }


@router.post("/narrate", response_model=CausalNarrateResult)
async def narrate_causal(body: CausalNarrateRequest):
    dag = build_domain_dag()
    fit_metadata: dict | None = None

    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT dag_json, fit_metadata FROM causal_models WHERE id = $1",
            body.model_id,
        )

    if row and row["dag_json"]:
        dag_json = row["dag_json"]
        dag_data = json.loads(dag_json) if isinstance(dag_json, str) else dag_json
        dag = dag_from_serializable(dag_data)
    if row and row["fit_metadata"]:
        fit_metadata_raw = row["fit_metadata"]
        fit_metadata = json.loads(fit_metadata_raw) if isinstance(fit_metadata_raw, str) else fit_metadata_raw

    if body.target_variable not in dag.nodes:
        raise HTTPException(status_code=400, detail="Target variable not in DAG")

    attributions: dict[str, float] = {}
    if _reasoner.is_fitted(body.model_id):
        try:
            attribution_result = _reasoner.attribute(
                model_id=body.model_id,
                target_variable=body.target_variable,
            )
            attributions = {
                str(k): float(v)
                for k, v in attribution_result.get("attributions", {}).items()
            }
        except Exception:
            attributions = {}
    elif isinstance(fit_metadata, dict):
        raw_attr = fit_metadata.get("attributions")
        if isinstance(raw_attr, dict):
            attributions = {str(k): float(v) for k, v in raw_attr.items()}

    from app.services.causal_narrator import CausalNarrator
    narrator = CausalNarrator()
    narrative = await narrator.generate_narrative(
        dag=dag,
        target_variable=body.target_variable,
        attributions=attributions,
        context=body.context,
    )

    path_count = 0
    for source in nx.ancestors(dag, body.target_variable):
        if path_count >= 5:
            break
        try:
            for _ in nx.all_simple_paths(dag, source=source, target=body.target_variable):
                path_count += 1
                if path_count >= 5:
                    break
        except nx.NetworkXNoPath:
            continue

    max_attr = max(attributions.values()) if attributions else 0.0
    if max_attr >= 0.6:
        confidence = "high"
    elif max_attr >= 0.3:
        confidence = "medium"
    else:
        confidence = "low"

    return CausalNarrateResult(
        narrative=narrative,
        paths_used=path_count,
        confidence=confidence,
    )
