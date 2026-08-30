"""The (tool, args) -> Effect mapper, and the structural properties of an effect.

D-003 ranks effects rather than tools, so something has to turn a proposed call into the
consequences it would produce *before* it produces them. That something already exists:
every ``ToolSpec`` carries a pure ``declare(world, args)``, and a Phase 1 test asserts the
declaration agrees with what the handler actually does across 24 tool/argument cases. This
module is the TCB-side wrapper around it, and it exists to add exactly one thing that the
raw declarer cannot express: **the difference between "this call produces no effects" and
"I could not work out what this call produces".**

That distinction is load-bearing. Under deny-by-default (D-004), authorization is a
membership test over the declared effect classes. An empty list passes that test
vacuously — no effects, nothing to authorize, ALLOW. So a declarer that raises on a
malformed argument would fail *open*, which is the one direction a reference monitor may
never fail. ``EffectMapping.ok`` makes the failure explicit and the combinator turns it
into a BLOCK.

**Known and measured weakness.** The ontology is finite and hand-built, so an attacker may
express a harmful consequence in terms we mis-map (THREAT_MODEL 4.4, "semantic
laundering"). The mapper's accuracy is therefore a component-level metric we report, not
an assumption. What this module guarantees is narrower and worth stating precisely: the
mapper never silently returns *nothing* for a call that does something.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from agentfw.core.types import (
    Effect,
    EffectClass,
    Externality,
    ProposedAction,
    Reversibility,
)

Declarer = Callable[[str, dict[str, Any]], list[Effect]]


@dataclass(frozen=True)
class EffectMapping:
    """What a proposed action would do, or an explicit admission that we do not know."""

    tool: str
    effects: tuple[Effect, ...]
    ok: bool
    reason: str = ""

    @property
    def classes(self) -> frozenset[EffectClass]:
        return frozenset(e.effect_class for e in self.effects)

    @classmethod
    def failed(cls, tool: str, reason: str) -> EffectMapping:
        return cls(tool=tool, effects=(), ok=False, reason=reason)


class EffectMapper:
    """Maps proposals to effects through the registry's declarers.

    Takes a callable rather than a ``ToolRouter`` so the mapper can be unit-tested and
    replayed offline without a world.
    """

    def __init__(self, declare: Declarer) -> None:
        self._declare = declare

    def map(self, action: ProposedAction) -> EffectMapping:
        try:
            declared = self._declare(action.tool_name, action.args)
        except Exception as exc:
            return EffectMapping.failed(
                action.tool_name, f"declarer raised {type(exc).__name__}: {exc}"
            )
        if declared is None:
            return EffectMapping.failed(action.tool_name, "declarer returned None")
        if not declared:
            # A tool that genuinely produces nothing would still declare a READ. An empty
            # list means the registry did not recognise the call.
            return EffectMapping.failed(
                action.tool_name, "no effects declared; tool unknown or arguments unusable"
            )
        return EffectMapping(action.tool_name, tuple(declared), ok=True)


# ---------------------------------------------------------------------------
# Structural properties of an effect
# ---------------------------------------------------------------------------


def consequential(effect: Effect) -> bool:
    """Is this effect worth a human's attention if its authorization is unclear?

    A **structural predicate, not a score** (D-005). It reads two fields the tool already
    declared and combines them with `or`: an effect is consequential if undoing it costs
    something, or if somebody other than the user can see it. There are no weights and
    nothing to tune, which is the whole point — a hand-tuned threshold here would be the
    unfalsifiable risk score the project decided against.

    Magnitude deliberately does not appear. Scaling the decision by how *large* the
    consequence is belongs in Phase 4's cost model, where it is derived from stated costs
    rather than asserted here.
    """
    return (
        effect.reversibility is not Reversibility.REVERSIBLE
        or effect.externality is not Externality.NONE
    )


def describe(effect: Effect) -> str:
    """One line of firewall-derived prose about an effect, for the ASK rendering.

    Assembled from enum values and numbers only. No agent-authored text can reach it,
    which is half of what P4 requires; ``policy/ask.py`` enforces the other half.
    """
    parts = [f"{effect.verb.value.lower()} {effect.resource_class.value.lower()}"]
    if effect.resource_id:
        parts.append(f"on {effect.resource_id}")
    if effect.magnitude is not None:
        value = effect.magnitude.value
        rendered = f"{value:,.2f}" if effect.magnitude.unit == "usd" else f"{value:g}"
        parts.append(f"({rendered} {effect.magnitude.unit})")
    tags = []
    if effect.reversibility is not Reversibility.REVERSIBLE:
        tags.append(effect.reversibility.value.lower().replace("_", " "))
    if effect.externality is not Externality.NONE:
        tags.append(effect.externality.value.lower().replace("_", " "))
    if tags:
        parts.append("[" + ", ".join(tags) + "]")
    return " ".join(parts)
