"""Loader for the hand-written gold IntentScopes (D-023).

Phase 2 has no intent compiler — that is Phase 3 — so the scope has to come from
somewhere, and it comes from a person reading the utterance. These are labels of the same
kind as the scenario oracles: written by hand, checked in, and read by the evaluation
harness rather than by anything in ``agentfw/core``.

The loader is strict on purpose. A scenario without a gold scope raises rather than
defaulting to an empty one, because an empty scope authorizes nothing and would silently
turn a missing label into a spectacular-looking security result.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from agentfw.core.scope import Constraint, IntentScope, ec, scope_from_user_turn
from agentfw.core.types import EffectClass

# Deliberately *not* under suites/: ``load_suite`` rglobs that directory for scenario
# YAML, so a scope file living there would be parsed as a malformed scenario.
SCOPES_DIR = Path(__file__).parent / "scopes_data"

# The span id the agent loop assigns to the user's turn: system prompt is s001, the
# utterance is s002. Every gold grant is stamped with it, so the provenance invariant
# ("each authorized effect traces to a USER turn") holds from revision 0.
USER_TURN_SPAN = "s002"


class MissingGoldScope(KeyError):
    """No scope was written for this scenario/variant. Fail loudly, never default."""


def parse_effect_class(text: str) -> EffectClass:
    verb, _, resource = text.partition(":")
    if not resource:
        raise ValueError(f"effect class {text!r} must be written as VERB:RESOURCE_CLASS")
    return ec(verb.strip().upper(), resource.strip().upper())


def parse_constraint(raw: dict[str, Any]) -> Constraint:
    data = dict(raw)
    applies = data.pop("applies_to", None)
    for key in ("allowed_recipients", "allowed_domains", "globs"):
        if key in data:
            data[key] = tuple(data[key])
    return Constraint(
        applies_to=parse_effect_class(applies) if applies else None,
        **data,
    )


def build_scope(objective: str, raw: dict[str, Any]) -> IntentScope:
    return scope_from_user_turn(
        objective,
        [parse_effect_class(e) for e in raw.get("effects", [])],
        span_id=USER_TURN_SPAN,
        constraints=[parse_constraint(c) for c in raw.get("constraints", [])],
        open_questions=list(raw.get("open_questions", [])),
    )


class GoldScopes:
    """scenario_id -> variant_id -> raw scope block."""

    def __init__(self, data: dict[str, dict[str, Any]]) -> None:
        self.data = data

    @classmethod
    def load(cls, path: Path | None = None) -> GoldScopes:
        path = path or SCOPES_DIR / "dev.yaml"
        return cls(yaml.safe_load(path.read_text(encoding="utf-8")) or {})

    def scope_for(self, scenario_id: str, variant_id: str, objective: str) -> IntentScope:
        try:
            raw = self.data[scenario_id][variant_id]
        except KeyError as exc:
            raise MissingGoldScope(
                f"no gold scope for {scenario_id}::{variant_id}. Add one to "
                f"{SCOPES_DIR / 'dev.yaml'} rather than letting it default to empty."
            ) from exc
        return build_scope(objective, raw)

    def covers(self, scenario_id: str, variant_id: str) -> bool:
        return variant_id in self.data.get(scenario_id, {})
