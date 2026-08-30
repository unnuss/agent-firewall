"""The reference monitor: the object that sits in ``ToolRouter(guard=...)``.

Everything below this line in the stack is deterministic and everything above it is not,
which is the whole architecture in one sentence. The agent proposes; this decides; only
then does the world change.

**Order of operations for one proposed action.**

1. Map the call to the effects it would produce (``core/effects``). An unmappable call is
   a BLOCK, not an empty effect set — see that module for why the distinction matters.
2. Run the structural monitors over the trace, the scope and the mapping.
3. Combine into ALLOW / ASK / BLOCK (``policy/combinator``).
4. If ASK: render the request from firewall facts alone (``policy/ask``), spend one unit
   of the interruption budget, take the answer, and — only if it approved — widen the
   scope through ``expand_via_consent``, which is the sole widening path in the system.
   Then decide again against the new scope. The second decision is a real decision, not a
   rubber stamp: consent grants specific effect classes, so an approval that does not
   cover everything the call would do still fails.
5. Before returning ALLOW, assert P2 — every effect class about to execute is in the
   scope. A violation raises rather than logs, because P2 is a claim that it cannot
   happen (THREAT_MODEL section 5).
6. Write an audit event either way.

**Why the ASK is resolved synchronously here.** The Phase 1 ``Guard`` protocol is
``check(action, declared) -> str | None`` — allow, or a refusal string. That looks
two-valued, but ASK is not a third outcome the *router* needs to understand: it is a step
the monitor takes before arriving at one of the two. Resolving it inside ``check`` keeps
the Phase 1 seam and its test untouched, which is what PROJECT_STATE promised, and it
matches how a real deployment would behave — the tool call blocks while the human decides.

**One deviation from the seam as built.** ``ToolRouter.declare`` swallows declarer
exceptions and returns ``[]``. Under deny-by-default an empty effect list authorizes
vacuously, so trusting the router's ``declared`` argument would fail open. The firewall
therefore maps effects itself, through the same registry, and treats the router's list as
advisory. ``ToolRouter.declare_for`` exists for exactly this and is what the firewall
binds to.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agentfw.agent.trace import Trace
from agentfw.core.audit import AuditLog
from agentfw.core.effects import EffectMapper, EffectMapping
from agentfw.core.labels import evidence_spans
from agentfw.core.scope import IntentScope, ScopeViolation
from agentfw.core.types import Effect, ProposedAction, Verdict
from agentfw.monitors.base import Monitor, Signal
from agentfw.monitors.flow import FlowMonitor
from agentfw.monitors.integrity import IntegrityMonitor
from agentfw.policy import ask as ask_mod
from agentfw.policy.combinator import Decision, PolicyConfig, decide

REFUSAL_TEMPLATE = (
    "Blocked by the authorization layer: {reason}\n"
    "This action was not performed. If it is genuinely part of what was asked, say so in "
    "your final answer rather than trying a different tool to achieve the same effect."
)


@dataclass
class Firewall:
    """A reference monitor for one episode. Not reusable across episodes: the scope, the
    audit chain and the interruption budget are all per-episode state."""

    scope: IntentScope
    trace: Trace
    mapper: EffectMapper
    audit: AuditLog = field(default_factory=AuditLog)
    cfg: PolicyConfig = field(default_factory=PolicyConfig)
    reviewer: ask_mod.Reviewer | None = None
    monitors: list[Monitor] = field(default_factory=lambda: [IntegrityMonitor(), FlowMonitor()])
    # Ground truth for the scripted reviewer, keyed by effect class string. Supplied by
    # the evaluation harness; ``None`` in any real deployment, where a human answers.
    licensed_oracle: dict[str, bool] = field(default_factory=dict)
    asks_used: int = 0
    episode_id: str = ""

    def __post_init__(self) -> None:
        if self.episode_id and not self.audit.episode_id:
            self.audit.episode_id = self.episode_id

    # -- the Guard protocol -------------------------------------------------

    def check(self, action: ProposedAction, declared: list[Effect]) -> str | None:
        """Return None to allow, or the refusal text the agent will see."""
        decision, _mapping = self.evaluate(action)
        if decision.verdict is Verdict.ALLOW:
            return None
        return REFUSAL_TEMPLATE.format(reason=decision.explanation)

    # -- the full decision --------------------------------------------------

    def evaluate(self, action: ProposedAction) -> tuple[Decision, EffectMapping]:
        mapping = self.mapper.map(action)
        # The scope the *policy* decides against, captured before any consent widens it.
        # Logging the post-consent scope instead would make every approved ASK replay as
        # an ALLOW and hide the fact that a human was interrupted at all.
        decided_against = self.scope
        signals = self._run_monitors(action, mapping)
        policy = decide(
            action, mapping, decided_against, signals, asks_used=self.asks_used, cfg=self.cfg
        )
        decision = policy

        ask_text: str | None = None
        approved: bool | None = None

        if policy.verdict is Verdict.ASK:
            ask_text, approved, decision = self._resolve_ask(action, mapping, policy)

        if decision.verdict is Verdict.ALLOW:
            self._assert_p2(action, mapping)

        self._log(
            action,
            mapping,
            decision,
            policy=policy,
            decided_against=decided_against,
            ask_text=ask_text,
            approved=approved,
        )
        return decision, mapping

    # -- internals ----------------------------------------------------------

    def _run_monitors(self, action: ProposedAction, mapping: EffectMapping) -> list[Signal]:
        spans = self.trace.ingested()
        return [m.evaluate(action, spans, self.scope, mapping) for m in self.monitors]

    def _resolve_ask(
        self, action: ProposedAction, mapping: EffectMapping, decision: Decision
    ) -> tuple[str, bool | None, Decision]:
        """Spend one interruption. Returns (rendered text, answer, final decision)."""
        request = ask_mod.build_request(
            call_id=action.call_id,
            step=action.step,
            tool=action.tool_name,
            args=action.args,
            effects=mapping.effects,
            would_grant=decision.would_grant,
            reason=decision.explanation,
            scope=self.scope,
            evidence_spans=evidence_spans(action.args, self.trace.ingested()),
            budget_remaining=max(self.cfg.ask_budget - self.asks_used, 0),
        )
        text = ask_mod.render(request)
        self.asks_used += 1

        if self.reviewer is None:
            # No consent channel configured. The question stands unanswered, and an
            # unanswered question is not permission.
            return (
                text,
                None,
                decision.model_copy(
                    update={
                        "verdict": Verdict.BLOCK,
                        "decided_by": "ask_unanswered",
                        "explanation": decision.explanation
                        + "; no reviewer available to answer",
                    }
                ),
            )

        record = self.reviewer.review(request, licensed=self._ground_truth(mapping))
        self.scope = self.scope.expand_via_consent(record)
        if not record.approved:
            return (
                text,
                False,
                decision.model_copy(
                    update={
                        "verdict": Verdict.BLOCK,
                        "decided_by": "consent_refused",
                        "explanation": decision.explanation + "; the user declined",
                    }
                ),
            )

        # Re-decide against the widened scope. Consent grants named effect classes, so a
        # partial approval that does not cover every declared effect still fails here.
        signals = self._run_monitors(action, mapping)
        second = decide(
            action, mapping, self.scope, signals, asks_used=self.asks_used, cfg=self.cfg
        )
        if second.verdict is Verdict.ASK:
            # Asking twice about one call would spend the budget without deciding
            # anything, and is a foothold for ASK flooding (THREAT_MODEL A6).
            return (
                text,
                True,
                second.model_copy(
                    update={
                        "verdict": Verdict.BLOCK,
                        "decided_by": "ask_not_settled",
                        "explanation": second.explanation
                        + "; consent did not cover every declared effect",
                    }
                ),
            )
        return (
            text,
            True,
            second.model_copy(update={"decided_by": f"{second.decided_by}+consent"}),
        )

    def _ground_truth(self, mapping: EffectMapping) -> bool | None:
        """Was every out-of-scope effect here in fact licensed by the user's utterance?

        Read from the scenario's own construction (AF-Auth ground truth is structural, by
        D-010), never inferred. Absent means the harness does not know, and the reviewer
        treats not-knowing as not-licensed.
        """
        if not self.licensed_oracle:
            return None
        pending = [
            str(e.effect_class)
            for e in mapping.effects
            if e.effect_class not in self.scope.authorized_effects
        ]
        if not pending:
            return True
        answers = [self.licensed_oracle.get(k) for k in pending]
        if any(a is None for a in answers):
            return None
        return all(answers)

    def _assert_p2(self, action: ProposedAction, mapping: EffectMapping) -> None:
        """P2: every executed effect class is in scope at execution time.

        A crash, not a log line. If this ever fires it means the combinator returned ALLOW
        for something deny-by-default should have caught, and every security claim in the
        project would be void until it is explained.
        """
        if not mapping.ok:
            raise ScopeViolation(
                f"P2 violated: {action.tool_name} was allowed with an unmapped effect set"
            )
        outside = [
            str(e.effect_class)
            for e in mapping.effects
            if e.effect_class not in self.scope.authorized_effects
        ]
        if outside:
            raise ScopeViolation(
                f"P2 violated: {action.tool_name} allowed with {outside} outside the scope "
                f"({self.scope.digest()})"
            )

    def _log(
        self,
        action: ProposedAction,
        mapping: EffectMapping,
        decision: Decision,
        *,
        policy: Decision,
        decided_against: IntentScope,
        ask_text: str | None,
        approved: bool | None,
    ) -> None:
        self.audit.append(
            episode_id=self.episode_id,
            call_id=action.call_id,
            step=action.step,
            tool=action.tool_name,
            args=action.args,
            arg_integrity=action.arg_label.integrity.value,
            arg_confidentiality=action.arg_label.confidentiality.value,
            evidence_spans=action.derived_from,
            effects=mapping.effects,
            mapping_ok=mapping.ok,
            mapping_reason=mapping.reason,
            scope=decided_against,
            scope_digest=decided_against.digest(),
            signals=tuple(s.as_dict() for s in policy.signals),
            gates_fired=policy.gates_fired,
            policy_verdict=policy.verdict,
            verdict=decision.verdict,
            decided_by=decision.decided_by,
            explanation=decision.explanation,
            ask_text=ask_text,
            consent_approved=approved,
            ask_budget_remaining=max(self.cfg.ask_budget - self.asks_used, 0),
            scope_revision_after=self.scope.revision,
        )


def build_firewall(
    *,
    scope: IntentScope,
    trace: Trace,
    router: Any,
    episode_id: str = "",
    cfg: PolicyConfig | None = None,
    reviewer: ask_mod.Reviewer | None = None,
    licensed_oracle: dict[str, bool] | None = None,
) -> Firewall:
    """Wire a firewall to a router. The router supplies the effect declarations."""
    return Firewall(
        scope=scope,
        trace=trace,
        mapper=EffectMapper(router.declare_for),
        cfg=cfg or PolicyConfig(),
        reviewer=reviewer,
        licensed_oracle=licensed_oracle or {},
        episode_id=episode_id,
        audit=AuditLog(episode_id),
    )
