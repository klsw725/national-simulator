"""DecisionEngine — rule-based geopolitical state transitions.

No LLM dependency. Pure rule evaluation:
  1. Update threat perception from events
  2. Evaluate objectives feasibility
  3. Filter by constraints
  4. Select optimal action
"""

from __future__ import annotations

import logging
from typing import Any

from app.geopolitics.actors import GeopoliticalActorState
from app.geopolitics.events import (
    CASCADE_DECAY,
    CASCADE_RULES,
    GeopoliticsEvent,
    MAX_CASCADE_DEPTH,
    PROPAGATION_RULES,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Decision thresholds
# ---------------------------------------------------------------------------
THREAT_ESCALATION_THRESHOLD = 0.6
RESOURCE_CRISIS_THRESHOLD = 0.3
PRESSURE_REVOLT_THRESHOLD = 0.8

# ---------------------------------------------------------------------------
# Action types the engine can decide
# ---------------------------------------------------------------------------
POSSIBLE_ACTIONS = [
    "military_movement",
    "military_exercise",
    "sanction_impose",
    "trade_restriction",
    "diplomatic_statement",
    "treaty_sign",
    "do_nothing",
]


class DecisionEngine:
    """Rule-based geopolitical decision engine."""

    def __init__(self) -> None:
        self._actors: dict[str, GeopoliticalActorState] = {}
        self._event_log: list[GeopoliticsEvent] = []
        self._round: int = 0

    def add_actor(self, actor: GeopoliticalActorState) -> None:
        self._actors[actor.actor_id] = actor

    def get_actor(self, actor_id: str) -> GeopoliticalActorState | None:
        return self._actors.get(actor_id)

    def get_all_actors(self) -> list[GeopoliticalActorState]:
        return list(self._actors.values())

    def get_event_log(self) -> list[GeopoliticsEvent]:
        return list(self._event_log)

    def apply_event(self, event: GeopoliticsEvent) -> dict[str, dict[str, float]]:
        """Apply an event's effects to target actors. Returns {actor_id: {field: delta}}."""
        deltas: dict[str, dict[str, float]] = {}
        rules = PROPAGATION_RULES.get(event.event_type, {})

        for target_id in event.target_actor_ids:
            actor = self._actors.get(target_id)
            if not actor:
                continue

            actor_deltas: dict[str, float] = {}
            for field_name, base_delta in rules.items():
                scaled = base_delta * event.magnitude

                # Allies of source feel less threat, adversaries feel more
                if field_name == "threat_perception":
                    if event.source_actor_id in actor.allies:
                        scaled *= 0.3
                    elif event.source_actor_id in actor.adversaries:
                        scaled *= 1.5

                old_val = getattr(actor, field_name)
                setattr(actor, field_name, old_val + scaled)
                actor.clamp_state()
                actor_deltas[field_name] = round(scaled, 4)

            deltas[target_id] = actor_deltas

        event.round_number = self._round
        self._event_log.append(event)
        return deltas

    def decide_actions(self) -> list[GeopoliticsEvent]:
        """Run one decision round for all actors. Returns generated events."""
        self._round += 1
        events: list[GeopoliticsEvent] = []

        for actor in self._actors.values():
            action = self._decide_single(actor)
            if action == "do_nothing":
                continue

            targets = self._select_targets(actor, action)
            if not targets:
                continue

            event = GeopoliticsEvent(
                event_type=action,
                source_actor_id=actor.actor_id,
                target_actor_ids=targets,
                magnitude=self._compute_magnitude(actor, action),
                description=f"{actor.name} initiates {action}",
                round_number=self._round,
            )
            events.append(event)
            actor.active_actions.append(action)

        return events

    def apply_event_with_cascade(
        self, event: GeopoliticsEvent, depth: int = 0,
    ) -> tuple[dict[str, dict[str, float]], list[GeopoliticsEvent]]:
        """Apply event + evaluate cascade triggers. Returns (deltas, cascade_events)."""
        deltas = self.apply_event(event)
        cascaded: list[GeopoliticsEvent] = []

        if depth >= MAX_CASCADE_DEPTH:
            return deltas, cascaded

        cascade_rules = CASCADE_RULES.get(event.event_type, [])
        for target_id in event.target_actor_ids:
            actor = self._actors.get(target_id)
            if not actor:
                continue

            for rule in cascade_rules:
                field_val = getattr(actor, rule["condition_field"], 0.0)
                triggered = (
                    (rule["condition_op"] == ">=" and field_val >= rule["condition_value"])
                    or (rule["condition_op"] == "<=" and field_val <= rule["condition_value"])
                )
                if not triggered:
                    continue

                cascade_targets = [
                    a for a in actor.adversaries
                    if a in self._actors and a != target_id
                ] or [event.source_actor_id]

                cascade_event = GeopoliticsEvent(
                    event_type=rule["trigger"],
                    source_actor_id=target_id,
                    target_actor_ids=cascade_targets,
                    magnitude=event.magnitude * rule["magnitude_factor"] * (CASCADE_DECAY ** depth),
                    description=rule["description"],
                    round_number=self._round,
                )
                cascaded.append(cascade_event)

                sub_deltas, sub_cascades = self.apply_event_with_cascade(
                    cascade_event, depth + 1,
                )
                for aid, d in sub_deltas.items():
                    deltas.setdefault(aid, {})
                    for k, v in d.items():
                        deltas[aid][k] = deltas[aid].get(k, 0.0) + v
                cascaded.extend(sub_cascades)

        return deltas, cascaded

    def run_round(self) -> dict[str, Any]:
        """Execute one full round: decide → apply (with cascade) → return summary."""
        decisions = self.decide_actions()

        all_deltas: dict[str, dict[str, float]] = {}
        all_cascades: list[GeopoliticsEvent] = []

        for event in decisions:
            deltas, cascades = self.apply_event_with_cascade(event)
            for actor_id, d in deltas.items():
                all_deltas.setdefault(actor_id, {})
                for k, v in d.items():
                    all_deltas[actor_id][k] = all_deltas[actor_id].get(k, 0.0) + v
            all_cascades.extend(cascades)

        return {
            "round": self._round,
            "events": [e.to_dict() for e in decisions],
            "cascade_events": [e.to_dict() for e in all_cascades],
            "state_changes": all_deltas,
            "actor_states": {a.actor_id: a.to_dict() for a in self._actors.values()},
        }

    def run_simulation(self, rounds: int) -> dict[str, Any]:
        """Execute N rounds and return full timeline."""
        timeline: list[dict[str, Any]] = []
        for _ in range(rounds):
            round_result = self.run_round()
            timeline.append(round_result)
        return {
            "total_rounds": rounds,
            "timeline": timeline,
            "final_states": {a.actor_id: a.to_dict() for a in self._actors.values()},
            "total_events": len(self._event_log),
        }

    # ------------------------------------------------------------------
    # Decision logic (rule-based, no LLM)
    # ------------------------------------------------------------------

    def _decide_single(self, actor: GeopoliticalActorState) -> str:
        # High threat + has adversaries → military response
        if actor.threat_perception >= THREAT_ESCALATION_THRESHOLD and actor.adversaries:
            if not self._has_hard_constraint(actor, "no_military"):
                if actor.resource_level >= 0.4:
                    return "military_movement"
                return "military_exercise"

        # Low resources → sanction adversaries (if able)
        if actor.resource_level <= RESOURCE_CRISIS_THRESHOLD and actor.adversaries:
            if not self._has_hard_constraint(actor, "no_sanctions"):
                return "trade_restriction"

        # High domestic pressure → diplomatic action
        if actor.domestic_pressure >= PRESSURE_REVOLT_THRESHOLD:
            return "diplomatic_statement"

        # Moderate threat → exercise
        if actor.threat_perception >= 0.4 and actor.adversaries:
            return "military_exercise"

        # Low threat + allies → strengthen alliance
        if actor.threat_perception <= 0.2 and actor.allies:
            return "treaty_sign"

        return "do_nothing"

    def _select_targets(self, actor: GeopoliticalActorState, action: str) -> list[str]:
        if action in ("military_movement", "military_exercise", "sanction_impose", "trade_restriction"):
            return [a for a in actor.adversaries if a in self._actors]
        if action == "diplomatic_statement":
            return [a_id for a_id in self._actors if a_id != actor.actor_id]
        if action == "treaty_sign":
            return [a for a in actor.allies if a in self._actors]
        return []

    def _compute_magnitude(self, actor: GeopoliticalActorState, action: str) -> float:
        base = 0.5
        if action in ("military_movement", "sanction_impose"):
            base = 0.3 + actor.threat_perception * 0.5
        elif action in ("military_exercise", "trade_restriction"):
            base = 0.2 + actor.threat_perception * 0.3
        elif action == "diplomatic_statement":
            base = 0.2 + actor.domestic_pressure * 0.3
        elif action == "treaty_sign":
            base = 0.3
        return round(min(1.0, base), 3)

    @staticmethod
    def _has_hard_constraint(actor: GeopoliticalActorState, constraint_name: str) -> bool:
        return any(c.name == constraint_name and c.hard for c in actor.constraints)
