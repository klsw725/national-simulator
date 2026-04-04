"""DecisionEngine — rule-based geopolitical state transitions.

Copied from backend/app/geopolitics/engine.py for service independence.
Extended with v12 action type propagation rules.
"""

from __future__ import annotations

import logging
from typing import Any

from app.engine.actors import GeopoliticalActorState
from app.engine.events import (
    CASCADE_DECAY,
    CASCADE_RULES,
    GeopoliticsEvent,
    MAX_CASCADE_DEPTH,
    PROPAGATION_RULES,
)

logger = logging.getLogger(__name__)

THREAT_ESCALATION_THRESHOLD = 0.6
RESOURCE_CRISIS_THRESHOLD = 0.3
PRESSURE_REVOLT_THRESHOLD = 0.8


class DecisionEngine:
    def __init__(self) -> None:
        self._actors: dict[str, GeopoliticalActorState] = {}
        self._event_log: list[GeopoliticsEvent] = []
        self._round: int = 0
        self._action_overrides: dict[str, str] = {}

    def add_actor(self, actor: GeopoliticalActorState) -> None:
        self._actors[actor.actor_id] = actor

    def get_actor(self, actor_id: str) -> GeopoliticalActorState | None:
        return self._actors.get(actor_id)

    def get_all_actors(self) -> list[GeopoliticalActorState]:
        return list(self._actors.values())

    def get_tension_levels(self) -> dict[str, float]:
        return {a.actor_id: a.threat_perception for a in self._actors.values()}

    def override_next_action(self, actor_id: str, action: str) -> None:
        self._action_overrides[actor_id] = action

    def apply_event(self, event: GeopoliticsEvent) -> dict[str, dict[str, float]]:
        deltas: dict[str, dict[str, float]] = {}
        rules = PROPAGATION_RULES.get(event.event_type, {})

        for target_id in event.target_actor_ids:
            actor = self._actors.get(target_id)
            if not actor:
                continue

            actor_deltas: dict[str, float] = {}
            for field_name, base_delta in rules.items():
                scaled = base_delta * event.magnitude
                if field_name == "threat_perception":
                    if event.source_actor_id in actor.allies:
                        scaled *= 0.3
                    elif event.source_actor_id in actor.adversaries:
                        scaled *= 1.5

                old_val = getattr(actor, field_name, 0.0)
                setattr(actor, field_name, old_val + scaled)
                actor.clamp_state()
                actor_deltas[field_name] = round(scaled, 4)

            deltas[target_id] = actor_deltas

        event.round_number = self._round
        self._event_log.append(event)
        return deltas

    def apply_event_with_cascade(
        self, event: GeopoliticsEvent, depth: int = 0,
    ) -> tuple[dict[str, dict[str, float]], list[GeopoliticsEvent]]:
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
                    a for a in actor.adversaries if a in self._actors and a != target_id
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
                sub_deltas, sub_cascades = self.apply_event_with_cascade(cascade_event, depth + 1)
                for aid, d in sub_deltas.items():
                    deltas.setdefault(aid, {})
                    for k, v in d.items():
                        deltas[aid][k] = deltas[aid].get(k, 0.0) + v
                cascaded.extend(sub_cascades)

        return deltas, cascaded

    def run_single_round(self, round_actions: list[dict]) -> dict[str, Any]:
        self._round += 1
        all_deltas: dict[str, dict[str, float]] = {}
        all_cascades: list[GeopoliticsEvent] = []

        for action in round_actions:
            targets = [a_id for a_id in self._actors if a_id != action.get("actor")]
            if action.get("target") and action["target"] in self._actors:
                targets = [action["target"]]

            event = GeopoliticsEvent(
                event_type=action.get("action_type", "do_nothing"),
                source_actor_id=action.get("actor", ""),
                target_actor_ids=targets,
                magnitude={"low": 0.3, "medium": 0.5, "high": 0.8}.get(
                    action.get("intensity", "medium"), 0.5,
                ),
                description=action.get("reasoning", ""),
                round_number=self._round,
            )
            deltas, cascades = self.apply_event_with_cascade(event)
            for aid, d in deltas.items():
                all_deltas.setdefault(aid, {})
                for k, v in d.items():
                    all_deltas[aid][k] = all_deltas[aid].get(k, 0.0) + v
            all_cascades.extend(cascades)

        self._action_overrides.clear()
        return {
            "round": self._round,
            "state_changes": all_deltas,
            "cascade_events": [e.to_dict() for e in all_cascades],
            "actor_states": {a.actor_id: a.to_dict() for a in self._actors.values()},
        }

    def serialize_state(self) -> dict:
        return {
            "actors": {aid: actor.to_dict() for aid, actor in self._actors.items()},
            "event_log": [e.to_dict() for e in self._event_log],
            "round": self._round,
        }

    @classmethod
    def from_state(cls, state: dict) -> DecisionEngine:
        engine = cls()
        engine._actors = {
            actor_id: GeopoliticalActorState.from_dict(actor_state)
            for actor_id, actor_state in state.get("actors", {}).items()
        }
        engine._event_log = [
            GeopoliticsEvent.from_dict(e) for e in state.get("event_log", [])
        ]
        engine._round = int(state.get("round", 0))
        return engine
