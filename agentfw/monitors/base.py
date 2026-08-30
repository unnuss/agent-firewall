"""The Monitor protocol and the Signal it produces.

One field here does the work of an architectural decision. ``Signal.structural`` says
whether a signal comes from the deterministic core or from something outside it, and the
combinator honours the difference absolutely:

* a **structural** signal may force BLOCK, and nothing else;
* a **non-structural** signal may move a decision only *within* the band the structural
  gates already permit, and may never turn a BLOCK into an ALLOW or an ASK.

That is D-006 — "no ML component can grant authority" — written as a type rather than as a
paragraph in a design document. In Phase 2 every monitor is structural, so the distinction
buys nothing yet; it exists now because retrofitting it in Phase 3, once the ML monitors
arrive and the temptation to let a confident classifier unblock something is live, would
be exactly the wrong time to be inventing the rule.

``Disposition`` is deliberately not a ``Verdict``. A monitor answers a narrow question
about one concern and has no business naming the outcome; the combinator owns that.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict

from agentfw.core.effects import EffectMapping
from agentfw.core.scope import IntentScope
from agentfw.core.types import ProposedAction, TraceSpan


class Disposition(StrEnum):
    """What one monitor thinks about one action, in its own narrow terms."""

    PERMIT = "PERMIT"  # nothing objectionable from this monitor's viewpoint
    ESCALATE = "ESCALATE"  # this monitor cannot settle it; a human might
    DENY = "DENY"  # this monitor objects


class Signal(BaseModel):
    """A monitor's contribution, with the evidence a human would need to check it."""

    model_config = ConfigDict(frozen=True)

    monitor: str
    disposition: Disposition
    # True only for deterministic TCB monitors. See the module docstring.
    structural: bool
    # Present for ML monitors from Phase 3 onward; None means "not a probabilistic claim".
    confidence: float | None = None
    # Span ids a reviewer can open to see why. Never free text from the agent.
    evidence: tuple[str, ...] = ()
    explanation: str = ""

    def as_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class Monitor(Protocol):
    """Every monitor answers the same question shape about a proposed action."""

    name: str

    def evaluate(
        self,
        action: ProposedAction,
        spans: list[TraceSpan],
        scope: IntentScope,
        mapping: EffectMapping,
    ) -> Signal: ...
