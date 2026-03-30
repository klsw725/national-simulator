from __future__ import annotations

import logging
from typing import Any

import networkx as nx
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class CausalReasoner:
    _shared_fitted_models: dict[str, Any] = {}
    _shared_fit_ranges: dict[str, dict[str, dict[str, float]]] = {}

    def __init__(self):
        self._fitted_models = self._shared_fitted_models
        self._fit_ranges = self._shared_fit_ranges

    @staticmethod
    def _import_gcm():
        try:
            import dowhy.gcm as gcm
        except ImportError as exc:
            raise ImportError("DoWhy GCM is required. Install dependency: dowhy>=0.11") from exc
        return gcm

    @staticmethod
    def _build_data_driven_dag(numeric_cols: list[str]) -> nx.DiGraph:
        """Build a DAG from observation columns using domain-informed ordering.

        Ordering heuristic: exogenous inputs first, derived/outcome vars last.
        """
        priority: dict[str, int] = {
            "geo_event_count": 0,
            "actor_activity": 0,
            "action_diversity": 1,
            "tension_ratio": 2,
            "escalation_level": 3,
        }
        ordered = sorted(
            numeric_cols,
            key=lambda c: priority.get(c, 1),
        )

        g = nx.DiGraph()
        g.add_nodes_from(ordered)
        for i, src in enumerate(ordered):
            for tgt in ordered[i + 1 :]:
                g.add_edge(src, tgt)
        return g

    def fit(self, model_id: str, dag: nx.DiGraph, df: pd.DataFrame) -> dict:
        gcm = self._import_gcm()

        variable_nodes = [
            node
            for node, attrs in dag.nodes(data=True)
            if attrs.get("node_type") in (None, "state")
        ]
        common_vars = [column for column in df.columns if column in variable_nodes]

        if common_vars:
            subgraph = dag.subgraph(common_vars).copy()
        else:
            numeric_cols = [
                col
                for col in df.select_dtypes(include="number").columns
                if col not in ("round_num",)
            ]
            if len(numeric_cols) < 2:
                raise ValueError("No common variables between DAG and dataframe")
            logger.info(
                "No overlap with domain DAG — building data-driven DAG from columns: %s",
                numeric_cols,
            )
            subgraph = self._build_data_driven_dag(numeric_cols)
            common_vars = list(subgraph.nodes)

        if not nx.is_directed_acyclic_graph(subgraph):
            raise ValueError("Selected subgraph is not a DAG")

        fit_df = df[common_vars].copy()
        scm = gcm.InvertibleStructuralCausalModel(subgraph)

        if len(fit_df) < 5:
            from dowhy.gcm.ml import create_linear_regressor

            for node in subgraph.nodes:
                if subgraph.in_degree(node) == 0:
                    scm.set_causal_mechanism(node, gcm.EmpiricalDistribution())
                else:
                    scm.set_causal_mechanism(
                        node,
                        gcm.AdditiveNoiseModel(create_linear_regressor()),
                    )
        else:
            gcm.auto.assign_causal_mechanisms(scm, fit_df)

        gcm.fit(scm, fit_df)

        self._fitted_models[model_id] = scm
        self._fit_ranges[model_id] = {
            "min": {k: float(v) for k, v in fit_df.min().to_dict().items()},
            "max": {k: float(v) for k, v in fit_df.max().to_dict().items()},
        }

        return {
            "model_id": model_id,
            "variables": common_vars,
            "observations": int(len(fit_df)),
            "status": "fitted",
        }

    def intervene(
        self,
        model_id: str,
        interventions: dict[str, float],
        target_variables: list[str] | None = None,
        num_samples: int = 500,
    ) -> dict:
        gcm = self._import_gcm()
        scm = self._fitted_models.get(model_id)
        if scm is None:
            raise ValueError(f"Causal model not fitted: {model_id}")

        intervention_dict = {var: (lambda _, v=val: v) for var, val in interventions.items()}
        samples = gcm.interventional_samples(scm, intervention_dict, num_samples_to_draw=num_samples)
        targets = target_variables or list(samples.columns)

        target_stats: dict[str, dict[str, float]] = {}
        for target in targets:
            if target not in samples.columns:
                continue
            series = samples[target]
            target_stats[target] = {
                "mean": float(series.mean()),
                "std": float(series.std()),
                "ci_lower": float(np.percentile(series, 5)),
                "ci_upper": float(np.percentile(series, 95)),
            }

        return {
            "interventions": interventions,
            "targets": target_stats,
            "num_samples": int(num_samples),
        }

    def counterfactual(
        self,
        model_id: str,
        observed: dict[str, float],
        interventions: dict[str, float],
    ) -> dict:
        gcm = self._import_gcm()
        scm = self._fitted_models.get(model_id)
        if scm is None:
            raise ValueError(f"Causal model not fitted: {model_id}")

        observed_df = pd.DataFrame([observed])
        graph = getattr(scm, "graph", None)
        if graph is not None:
            observed_df = observed_df.reindex(columns=list(graph.nodes), fill_value=0.0)

        intervention_dict = {var: (lambda _, v=val: v) for var, val in interventions.items()}
        cf = gcm.counterfactual_samples(scm, intervention_dict, observed_df)
        counterfactual_values = {k: float(v) for k, v in cf.iloc[0].to_dict().items()}
        differences = {
            key: float(counterfactual_values[key] - observed.get(key, 0.0))
            for key in counterfactual_values
        }

        return {
            "observed": observed,
            "counterfactual": counterfactual_values,
            "differences": differences,
        }

    def attribute(
        self,
        model_id: str,
        target_variable: str,
        df: pd.DataFrame | None = None,
    ) -> dict:
        gcm = self._import_gcm()
        scm = self._fitted_models.get(model_id)
        if scm is None:
            raise ValueError(f"Causal model not fitted: {model_id}")

        graph = getattr(scm, "graph", None)
        if graph is None:
            raise ValueError("SCM graph is unavailable")
        if target_variable not in graph:
            raise ValueError(f"Target variable not in model: {target_variable}")

        parents = list(graph.predecessors(target_variable))
        if not parents:
            return {
                "target_variable": target_variable,
                "attributions": {},
                "total_explained": 0.0,
                "method": "intervention_range",
            }

        baseline_samples = gcm.interventional_samples(scm, {}, num_samples_to_draw=200)
        if target_variable not in baseline_samples.columns:
            raise ValueError(f"Target variable not sampled: {target_variable}")
        baseline = float(baseline_samples[target_variable].mean())

        min_map = self._fit_ranges.get(model_id, {}).get("min", {})
        max_map = self._fit_ranges.get(model_id, {}).get("max", {})
        if df is not None:
            min_map = {**min_map, **{k: float(v) for k, v in df.min().to_dict().items()}}
            max_map = {**max_map, **{k: float(v) for k, v in df.max().to_dict().items()}}

        raw_contributions: dict[str, float] = {}
        for parent in parents:
            low_val = float(min_map.get(parent, 0.1))
            high_val = float(max_map.get(parent, 0.9))
            if np.isclose(high_val, low_val):
                high_val = low_val + 1e-6

            high_samples = gcm.interventional_samples(
                scm,
                {parent: (lambda _, v=high_val: v)},
                num_samples_to_draw=200,
            )
            low_samples = gcm.interventional_samples(
                scm,
                {parent: (lambda _, v=low_val: v)},
                num_samples_to_draw=200,
            )
            if target_variable not in high_samples.columns or target_variable not in low_samples.columns:
                continue

            effect_high = float(high_samples[target_variable].mean())
            effect_low = float(low_samples[target_variable].mean())
            contribution = abs(effect_high - effect_low)
            if contribution > 0:
                raw_contributions[parent] = contribution

        total = float(sum(raw_contributions.values()))
        if total > 0:
            attributions = {
                parent: float(value / total)
                for parent, value in raw_contributions.items()
            }
            explained = min(1.0, total / (abs(baseline) + 1e-6))
        else:
            attributions = {parent: 0.0 for parent in parents}
            explained = 0.0

        return {
            "target_variable": target_variable,
            "attributions": attributions,
            "total_explained": float(explained),
            "method": "intervention_range",
        }

    def is_fitted(self, model_id: str) -> bool:
        return model_id in self._fitted_models
