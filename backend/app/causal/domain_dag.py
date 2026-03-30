from __future__ import annotations

import networkx as nx

from app.geopolitics.events import CASCADE_RULES, PROPAGATION_RULES


def _add_or_append_condition(G: nx.DiGraph, source: str, target: str, condition: str) -> None:
    if G.has_edge(source, target):
        existing = G[source][target].get("conditions", [])
        G[source][target]["conditions"] = [*existing, condition]
        return
    G.add_edge(source, target, edge_type="decision_input", conditions=[condition])


def build_domain_dag() -> nx.DiGraph:
    """지정학 엔진의 규칙을 공식 인과 DAG로 변환."""
    G = nx.DiGraph()

    state_nodes = ["threat_perception", "domestic_pressure", "resource_level"]
    event_nodes = [
        "military_movement",
        "military_exercise",
        "sanction_impose",
        "trade_restriction",
        "diplomatic_statement",
        "treaty_sign",
        "official_response",
        "alliance_support",
    ]

    for node in state_nodes:
        G.add_node(node, node_type="state")

    for node in event_nodes:
        G.add_node(node, node_type="event")

    G.add_node("escalation_decision", node_type="decision")
    G.add_node("conflict_outcome", node_type="outcome")

    for event_type, state_deltas in PROPAGATION_RULES.items():
        if event_type not in G:
            G.add_node(event_type, node_type="event")
        for state_name, delta in state_deltas.items():
            if state_name not in G:
                G.add_node(state_name, node_type="state")
            G.add_edge(
                event_type,
                state_name,
                edge_type="propagates_to",
                strength=float(delta),
                provenance="PROPAGATION_RULES",
            )

    _add_or_append_condition(
        G,
        "threat_perception",
        "escalation_decision",
        "threat_perception >= 0.6 and adversaries -> military_movement",
    )
    _add_or_append_condition(
        G,
        "resource_level",
        "escalation_decision",
        "resource_level <= 0.3 and adversaries -> trade_restriction",
    )
    _add_or_append_condition(
        G,
        "domestic_pressure",
        "escalation_decision",
        "domestic_pressure >= 0.8 -> diplomatic_statement",
    )
    _add_or_append_condition(
        G,
        "threat_perception",
        "escalation_decision",
        "threat_perception >= 0.4 and adversaries -> military_exercise",
    )
    _add_or_append_condition(
        G,
        "threat_perception",
        "escalation_decision",
        "threat_perception <= 0.2 and allies -> treaty_sign",
    )

    for source_event, cascade_rules in CASCADE_RULES.items():
        if source_event not in G:
            G.add_node(source_event, node_type="event")
        for rule in cascade_rules:
            trigger = str(rule.get("trigger", ""))
            condition_field = str(rule.get("condition_field", ""))
            condition_op = str(rule.get("condition_op", ""))
            condition_value = rule.get("condition_value")
            magnitude_factor = rule.get("magnitude_factor")

            target_event = trigger
            if trigger == source_event:
                target_event = f"{trigger}_cascade"
                G.add_node(target_event, node_type="event_feedback", base_event=trigger)
            elif trigger and trigger not in G:
                G.add_node(trigger, node_type="event")

            if trigger:
                G.add_edge(
                    source_event,
                    target_event,
                    edge_type="cascades_to",
                    condition=f"{condition_field} {condition_op} {condition_value}",
                    probability=float(magnitude_factor) if magnitude_factor is not None else None,
                    provenance="CASCADE_RULES",
                )

    G.add_edge(
        "escalation_decision",
        "conflict_outcome",
        edge_type="determines",
    )

    assert nx.is_directed_acyclic_graph(G)
    return G


def dag_to_serializable(G: nx.DiGraph) -> dict:
    """NetworkX DAG를 JSON 직렬화 가능 dict로 변환."""
    return nx.node_link_data(G, edges="links")


def dag_from_serializable(data: dict) -> nx.DiGraph:
    """JSON dict에서 NetworkX DAG 복원."""
    return nx.node_link_graph(data, edges="links")
