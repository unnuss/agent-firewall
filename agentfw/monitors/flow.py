"""FlowMonitor — the deterministic declassification gate only.

**Scope of this file, stated because the roadmap splits it.** ROADMAP puts
``monitors/flow.py`` in Phase 4, but Phase 2 owes property tests for P1-P4, and P3 is a
flow claim:

    P3. Every SECRET-labeled value reaching an external-destination argument has an
    explicit declassification grant traceable to a USER turn.

So Phase 2 implements exactly enough to make P3 hold and be testable: compute the
confidentiality of the data literally present in the arguments, classify where the effect
sends it, and require a grant when the first exceeds what the second may observe. What
stays in Phase 4 is the rest of ARCHITECTURE 4.2 — the sensitive-pattern detector that
upgrades labels at ingestion for content arriving without a clear classification, and the
full lattice work around partial declassification.

**Precision choice.** Confidentiality is measured by literal containment, not by the
conservative context label. That is the exact test for the property being claimed: P3 is
about values that *reach* an argument, so a value that is not in the argument is not
reaching the destination. Using the conservative label instead would block any outbound
message sent after the agent so much as listed a SECRET file, which is over-blocking for
no gain in the property.

**Conceded, and not quietly.** Steganographic and encoded exfiltration inside an otherwise
authorized payload defeats literal matching — an agent that base64s a key into a
legitimate email body passes this gate. THREAT_MODEL 4.5 concedes exactly this. The gate
catches verbatim leakage, which is what the AF-Inject exfiltration scenarios do and what
real accidental leakage looks like; it is not a covert-channel defense and must never be
described as one.
"""

from __future__ import annotations

from agentfw.core.effects import EffectMapping
from agentfw.core.labels import (
    Destination,
    carried_confidentiality,
    destination_of,
    evidence_spans,
)
from agentfw.core.scope import IntentScope
from agentfw.core.types import Confidentiality, ProposedAction, TraceSpan
from agentfw.monitors.base import Disposition, Signal


class FlowMonitor:
    """Deterministic confidentiality gate. In the TCB; no model calls."""

    name = "flow"

    def evaluate(
        self,
        action: ProposedAction,
        spans: list[TraceSpan],
        scope: IntentScope,
        mapping: EffectMapping,
    ) -> Signal:
        outbound = [e for e in mapping.effects if destination_of(e) is not Destination.LOCAL]
        if not outbound:
            return Signal(
                monitor=self.name,
                disposition=Disposition.PERMIT,
                structural=True,
                explanation="no effect here sends data outside the user's own account",
            )

        conf = carried_confidentiality(action.args, spans)
        supporting = evidence_spans(action.args, spans)
        worst = max(outbound, key=lambda e: destination_of(e).rank())
        destination = destination_of(worst)

        permitted, reason = scope.permits_flow(conf, destination)
        if permitted:
            return Signal(
                monitor=self.name,
                disposition=Disposition.PERMIT,
                structural=True,
                evidence=tuple(s.id for s in supporting),
                explanation=reason,
            )

        # A public destination is not a judgement call: nothing above PUBLIC may go there
        # without a grant, and no human should be asked to approve it action by action.
        # A named third party is where an interruption can genuinely resolve the question.
        deny = destination is Destination.PUBLIC or conf is Confidentiality.SECRET
        return Signal(
            monitor=self.name,
            disposition=Disposition.DENY if deny else Disposition.ESCALATE,
            structural=True,
            evidence=tuple(s.id for s in supporting),
            explanation=reason,
        )
