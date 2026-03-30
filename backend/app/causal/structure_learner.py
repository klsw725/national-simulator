from __future__ import annotations

from collections import Counter

import networkx as nx
import pandas as pd
from pgmpy.estimators import BDeu, HillClimbSearch
from sklearn.preprocessing import KBinsDiscretizer


class CausalStructureLearner:
    def learn_structure(
        self,
        df: pd.DataFrame,
        n_bootstrap: int = 50,
        stability_threshold: float = 0.7,
    ) -> nx.DiGraph:
        if len(df) < 30:
            raise ValueError("At least 30 rows are required for causal structure learning")

        if n_bootstrap < 1:
            raise ValueError("n_bootstrap must be >= 1")

        numeric_df = df.select_dtypes(include=["number"]).copy()
        if numeric_df.empty:
            raise ValueError("No numeric columns available for structure learning")

        discretizer = KBinsDiscretizer(n_bins=5, encode="ordinal", strategy="quantile")
        transformed = discretizer.fit_transform(numeric_df)
        discrete_df = pd.DataFrame(
            transformed,
            columns=numeric_df.columns,
            index=numeric_df.index,
        ).round().astype(int)

        edge_counter: Counter[tuple[str, str]] = Counter()

        for i in range(n_bootstrap):
            sampled_df = discrete_df.sample(frac=1.0, replace=True, random_state=42 + i)
            estimator = HillClimbSearch(sampled_df)
            model = estimator.estimate(scoring_method=BDeu(sampled_df))
            for edge in model.edges():
                edge_counter[(str(edge[0]), str(edge[1]))] += 1

        edge_stability = {
            edge: count / n_bootstrap
            for edge, count in edge_counter.items()
        }

        learned = nx.DiGraph()
        learned.add_nodes_from(discrete_df.columns)
        kept_edges = [
            (u, v, stability)
            for (u, v), stability in edge_stability.items()
            if stability >= stability_threshold
        ]
        kept_edges.sort(key=lambda item: item[2], reverse=True)

        for u, v, stability in kept_edges:
            learned.add_edge(u, v, confidence=round(stability, 4), provenance="learned")
            if not nx.is_directed_acyclic_graph(learned):
                learned.remove_edge(u, v)

        return learned

    @staticmethod
    def compare_with_domain(learned_dag: nx.DiGraph, domain_dag: nx.DiGraph) -> dict:
        learned_edges = set(learned_dag.edges())
        domain_edges = set(domain_dag.edges())

        confirmed = sorted(learned_edges & domain_edges)
        discovered = sorted(learned_edges - domain_edges)
        missing = sorted(domain_edges - learned_edges)

        reversed_edges: list[tuple[str, str]] = []
        for u, v in learned_edges:
            if (v, u) in domain_edges:
                reversed_edges.append((u, v))

        return {
            "confirmed": confirmed,
            "discovered": sorted([e for e in discovered if (e[1], e[0]) not in domain_edges]),
            "missing": sorted([e for e in missing if (e[1], e[0]) not in learned_edges]),
            "reversed": sorted(reversed_edges),
        }

    @staticmethod
    def merge_dags(
        domain_dag: nx.DiGraph,
        learned_dag: nx.DiGraph,
        domain_priority: bool = True,
    ) -> nx.DiGraph:
        merged = domain_dag.copy()
        merged.add_nodes_from(learned_dag.nodes(data=True))

        for u, v, data in learned_dag.edges(data=True):
            reverse_exists = merged.has_edge(v, u)
            if reverse_exists and domain_priority:
                continue
            if reverse_exists and not domain_priority:
                merged.remove_edge(v, u)
            if not merged.has_edge(u, v):
                merged.add_edge(u, v, **data)

        if not nx.is_directed_acyclic_graph(merged):
            raise ValueError("Merged DAG contains cycles")

        return merged
