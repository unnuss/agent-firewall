"""PolicyCombinator: signals in, ALLOW / ASK / BLOCK out.

The shape of this module is the shape of D-005 and D-006, so it is worth being explicit
about what it deliberately is not. It is **not** a weighted sum over signals with tuned
coefficients. A hand-tuned risk score is unfalsifiable, fits itself to whichever demo you
last looked at, and is the single clearest tell of hackathon-grade work. Instead:

**Stage 1 — structural gates.** An ordered list of deterministic checks, each of which can
only ever force BLOCK. They are in the TCB, they never consult a model, and no later stage
can overturn one. This is where P1, P2 and P3 are enforced.

**Stage 2 — the decision proper.** In the finished system this is an expected-cost
comparison over ``C_block_benign``, ``C_allow_harmful(effect)`` and ``C_ask``, driven by a
calibrated ``P(licensed)``. That arrives in Phase 4, and its inputs arrive in Phase 3.

Phase 2 therefore ships a **placeholder** with no probability in it at all, because there
is no model yet to produce one. The placeholder is the M0 rule: in scope and within
constraints means ALLOW, and out of scope means ask a human if the consequence is worth an
interruption. "Worth an interruption" is ``effects.consequential`` — a structural predicate
over reversibility and externality, not a threshold anyone tuned.

That leaves exactly one knob, ``ask_on``, and it exists to be swept rather than set:
``consequential`` is the default, ``all_out_of_scope`` is the maximally cautious variant,
``never`` is pure deny-by-default with no human in the loop. Reporting all three in E-01a
costs one extra run and makes the placeholder's cost visible instead of asserted.

**What this predicts, and it is not flattering.** D-022 established that these agents
already respect explicit boundaries at ~0%. A membership test over effect classes catches
explicit violations. So on the control half of AF-Auth this combinator should prevent
almost nothing, because there was almost nothing to prevent. The band where the value is —
underspecified intent — is precisely where a membership test has no opinion beyond
"absent, therefore ask". Holding that prediction against E-01a is the point of running it.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from agentfw.core.effects import EffectMapping, consequential
from agentfw.core.scope import Constraint, ConstraintProvenance, IntentScope, ScopeCheck
from agentfw.core.types import ProposedAction, Verdict, most_restrictive
from agentfw.monitors.base import Disposition, Signal


class PolicyConfig(BaseModel):
    """Every tunable in the Phase 2 policy, which is deliberately almost none."""

    model_config = ConfigDict(frozen=True)

    # When an effect is out of scope, when is a human worth interrupting?
    ask_on: Literal["consequential", "all_out_of_scope", "never"] = "consequential"
    # Interruptions available per episode (D-009). Exhaustion fails closed.
    ask_budget: int = 3
    # Present so the fail-closed behaviour is visible in configs rather than implicit.
    # Setting it False contradicts D-009 and is rejected by a test; it exists so that an
    # ablation which changes it has to say so out loud.
    fail_closed_on_exhaustion: bool = True


class Decision(BaseModel):
    """The combinator's output, carrying enough to replay itself."""

    model_config = ConfigDict(frozen=True)

    verdict: Verdict
    decided_by: str
    gates_fired: tuple[str, ...] = ()
    explanation: str = ""
    signals: tuple[Signal, ...] = ()
    scope_checks: tuple[ScopeCheck, ...] = ()
    # The effect classes an ASK would have to grant for this action to proceed.
    would_grant: tuple[str, ...] = ()
    # Inferred bounds an ASK would have to lift for this action to proceed (D-030). Held as
    # the constraints themselves, because consent has to name exactly what it relaxes.
    relaxable: tuple[Constraint, ...] = ()


class _Gate(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    fired: bool
    reason: str = ""


def structural_gates(
    action: ProposedAction,
    mapping: EffectMapping,
    scope: IntentScope,
    signals: list[Signal],
    *,
    checks: list[ScopeCheck],
) -> list[_Gate]:
    """The BLOCK-only stage. Order is fixed so the audit log reads the same way every time.

    Every gate here is deterministic and reads only labels, enum fields and set
    membership. None of them can produce ALLOW — a gate that fired means BLOCK, and a gate
    that did not fire means "this gate has no objection", never "this gate approves".
    """
    gates: list[_Gate] = []

    # G0. We could not work out what this call would do. The one direction a reference
    # monitor may never fail is open, and an unmappable call is exactly that risk
    # (core/effects.py explains why an empty effect list would otherwise pass vacuously).
    gates.append(
        _Gate(
            name="G0_unmappable_action",
            fired=not mapping.ok,
            reason=mapping.reason,
        )
    )

    # G1. A structural monitor objected. Non-structural signals are ignored here by
    # construction: D-006 says ML may move a decision inside the permitted band, never
    # force one, and never expand authority.
    denials = [s for s in signals if s.structural and s.disposition is Disposition.DENY]
    gates.append(
        _Gate(
            name="G1_structural_denial",
            fired=bool(denials),
            reason="; ".join(f"{s.monitor}: {s.explanation}" for s in denials),
        )
    )

    # G2. The effect class is licensed but this instance breaches a bound **the user
    # stated** (THREAT_MODEL B2). A violated explicit constraint is not ambiguity, so it is
    # not a candidate for an interruption: the user already said where the line was.
    #
    # A bound the *compiler inferred* is a different object and is deliberately not here
    # (D-030, F-13). Violating a guess is not evidence the user drew a line, and routing it
    # through a hard gate makes it unrepairable — no interruption can lift a G2 — which
    # E-01b measured as the single largest source of utility loss under a real compiler.
    # Those breaches escalate in stage 2 instead, where a human can settle them.
    breaches = [
        c for c in checks if c.in_scope and not c.satisfied and c.user_constraint_failures
    ]
    gates.append(
        _Gate(
            name="G2_constraint_violation",
            fired=bool(breaches),
            reason="; ".join("; ".join(c.user_constraint_failures) for c in breaches),
        )
    )

    # The interruption budget (D-009) is *not* a gate here. It can only turn an ASK into a
    # BLOCK, so it has to run after stage 2 has decided whether there would be an ASK at
    # all; applying it up front would fire on actions that were never going to interrupt
    # anybody and would make the audit log say something untrue about why they stopped.
    return gates


def decide(
    action: ProposedAction,
    mapping: EffectMapping,
    scope: IntentScope,
    signals: list[Signal],
    *,
    asks_used: int = 0,
    cfg: PolicyConfig | None = None,
) -> Decision:
    """Run the gates, then the placeholder rule. Pure: same inputs, same verdict."""
    cfg = cfg or PolicyConfig()
    checks = [scope.satisfies(e, action.args) for e in mapping.effects]
    gates = structural_gates(action, mapping, scope, signals, checks=checks)
    fired = [g for g in gates if g.fired]
    if fired:
        return Decision(
            verdict=Verdict.BLOCK,
            decided_by="structural_gate",
            gates_fired=tuple(g.name for g in fired),
            explanation="; ".join(f"{g.name}: {g.reason}" for g in fired if g.reason)
            or fired[0].name,
            signals=tuple(signals),
            scope_checks=tuple(checks),
        )

    if not mapping.effects:  # unreachable while G0 fires, kept as defence in depth
        return Decision(
            verdict=Verdict.BLOCK,
            decided_by="structural_gate",
            gates_fired=("G0_unmappable_action",),
            explanation="no declared effects",
            signals=tuple(signals),
        )

    # -- stage 2: the placeholder. Phase 4 replaces this whole block. -------------
    per_effect: list[Verdict] = []
    reasons: list[str] = []
    to_grant: list[str] = []
    to_relax: list[Constraint] = []
    for effect, check in zip(mapping.effects, checks, strict=True):
        if check.satisfied:
            per_effect.append(Verdict.ALLOW)
            continue
        if check.only_compiler_bounds_failed:
            # The class is licensed; the only obstacle is a limit a model inferred (D-030).
            # That is a question, not a boundary, so it escalates rather than refusing —
            # and it escalates regardless of `consequential`, because the relevant fact is
            # not how large the consequence is but that nobody actually set this limit.
            to_relax.extend(
                c
                for c in scope.constraints
                if c.provenance is ConstraintProvenance.COMPILER
                and not c.check(effect, action.args)[0]
            )
            if cfg.ask_on == "never":
                per_effect.append(Verdict.BLOCK)
                reasons.append(f"{check.reason}; no ASK channel configured")
            else:
                per_effect.append(Verdict.ASK)
                reasons.append(f"{check.reason}; this limit was inferred, not stated")
            continue
        to_grant.append(str(effect.effect_class))
        if scope.refused(effect.effect_class):
            # Already put to the user this episode and declined (D-024). Asking again
            # would spend a second interruption to receive the same answer.
            per_effect.append(Verdict.BLOCK)
            reasons.append(f"{check.reason}; the user already declined this")
        elif cfg.ask_on == "never":
            per_effect.append(Verdict.BLOCK)
            reasons.append(f"{check.reason}; no ASK channel configured")
        elif cfg.ask_on == "all_out_of_scope" or consequential(effect):
            per_effect.append(Verdict.ASK)
            reasons.append(f"{check.reason}; the consequence warrants confirming")
        else:
            per_effect.append(Verdict.BLOCK)
            reasons.append(f"{check.reason}; reversible and unobservable, not worth an ASK")

    verdict = most_restrictive(per_effect)
    escalating = [
        s
        for s in signals
        if s.structural and s.disposition is Disposition.ESCALATE and verdict is Verdict.ALLOW
    ]
    if escalating and cfg.ask_on != "never":
        # A structural monitor may raise a question about an in-scope action — an
        # unauthorized data flow to a plausible third party is the case that matters.
        # It escalates; it cannot allow.
        verdict = Verdict.ASK
        reasons += [f"{s.monitor}: {s.explanation}" for s in escalating]

    # -- the interruption budget, applied last (D-009) ---------------------------
    # It can only make the verdict more restrictive. Fail-closed on exhaustion is the
    # correct answer to ASK flooding (THREAT_MODEL A6) and the only one consistent with
    # least privilege: an attacker who can spend the human's attention must not thereby
    # obtain an ALLOW.
    if verdict is Verdict.ASK and asks_used >= cfg.ask_budget:
        if not cfg.fail_closed_on_exhaustion:
            raise ValueError(
                "fail_closed_on_exhaustion=False contradicts D-009; an ablation that "
                "wants ASK-flooding to succeed must say so in DECISIONS.md first"
            )
        return Decision(
            verdict=Verdict.BLOCK,
            decided_by="structural_gate",
            gates_fired=("G3_ask_budget_exhausted",),
            explanation=(
                f"would have asked, but {asks_used}/{cfg.ask_budget} interruptions are "
                f"already spent this episode; failing closed. Pending: {'; '.join(reasons)}"
            ),
            signals=tuple(signals),
            scope_checks=tuple(checks),
            would_grant=tuple(dict.fromkeys(to_grant)),
            relaxable=tuple(dict.fromkeys(to_relax)),
        )

    return Decision(
        verdict=verdict,
        decided_by="placeholder_membership_rule",
        gates_fired=(),
        explanation="; ".join(reasons) or "every declared effect is authorized and in bounds",
        signals=tuple(signals),
        scope_checks=tuple(checks),
        would_grant=tuple(dict.fromkeys(to_grant)),
        relaxable=tuple(dict.fromkeys(to_relax)),
    )
