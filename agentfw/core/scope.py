"""IntentScope: what the user actually licensed, and the algebra over it.

This module carries the invariant the whole project rests on (PROJECT_SPEC 5.3, D-007):

    **Scope monotonicity.** The set of effects the agent may produce can be narrowed by
    anything. It can be widened only by a human answering an ASK, and every widening is
    recorded with USER provenance.

Progent (arXiv:2504.11703) enforces the equivalent with an SMT solver over a policy DSL.
We get it more cheaply because a scope here is a finite set of effect classes plus
declarative constraints, so "did this operation widen authority?" is set containment
rather than implication checking.

**How it is enforced, precisely.** Three mechanisms, because convention is not enforcement:

1. ``IntentScope`` is frozen. Nothing mutates a scope in place; every operation returns a
   new one, so a stale reference cannot be widened behind the monitor's back.
2. ``authorized_effects`` is *derived* from ``grants``. There is no way to hold an
   authorized effect class that is not backed by a ``Grant`` carrying the id of the span
   that licensed it. Provenance is not an annotation, it is the storage.
3. ``narrow()`` has no parameter capable of adding a grant, and ``expand_via_consent()``
   accepts only a ``ConsentRecord`` — whose validator rejects any label that is not USER.
   Untrusted content cannot construct one, which is P1.

A note on the boundary this does *not* police. Constructing a fresh ``IntentScope`` with
whatever grants you like is always possible, because that is what the intent compiler does
when it reads the user's utterance. The invariant is about *operations on an existing
scope during an episode*, which is where an attacker acts. Nothing untrusted reaches the
constructor: it is called once, from the utterance, before the agent runs.
"""

from __future__ import annotations

import fnmatch
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator

from agentfw.core.labels import Destination, exceeds_permitted
from agentfw.core.types import (
    Confidentiality,
    Effect,
    EffectClass,
    Integrity,
    Label,
    ResourceClass,
    Verb,
)


class ConstraintProvenance(StrEnum):
    """Who drew this line — and therefore what a violation of it means (D-030, F-13).

    ``USER`` is a bound stated in the user's own words: "under $150", "do not copy anyone
    else at Northwind". Violating it is THREAT_MODEL family B2, it is not ambiguity, and the
    correct response is to refuse without spending anybody's attention — the user already
    said where the line was.

    ``COMPILER`` is a bound an intent compiler *inferred*. A violation of it is not evidence
    that the user drew a line; it is evidence that a model guessed one. E-01b measured what
    treating the two identically costs: the registered compiler invented 127 bounds across
    three seeds and fired the hard G2 gate about 110 times per seed, blocking purchases and
    sends the utterance had explicitly authorized, and no interruption could repair any of
    them because a hard gate never reaches the ASK path.

    The distinction cannot be inferred from the constraint's contents, which is why it is
    stored rather than derived, and it defaults to ``USER`` so that a caller who forgets to
    set it gets the *more* restrictive treatment.
    """

    USER = "USER"
    COMPILER = "COMPILER"


class ScopeViolation(Exception):
    """Raised when an operation would widen authority without USER consent.

    An exception rather than a return value on purpose: P1 and P2 are claims that a
    violation *cannot happen*, so the failure mode is a crash the tests can assert on,
    never a log line somebody might filter out (THREAT_MODEL section 5).
    """


# ---------------------------------------------------------------------------
# Constraints
# ---------------------------------------------------------------------------


class Constraint(BaseModel):
    """A declarative bound on an authorized effect class.

    Constraints answer THREAT_MODEL family B2: the effect class is licensed, the specific
    instance is not — right verb, wrong recipient; right tool, over budget. They are
    checked against the *declared effect* and the normalized arguments, never against the
    agent's prose.

    One field is worth explaining. ``applies_to`` scopes a constraint to an effect class;
    ``None`` means it applies to every effect the check is run against. A budget attached
    to nothing in particular should bind every purchase in the episode, not just the first
    one anybody thought of.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    # One of: budget, recipient, domain, time_window, resource_glob, magnitude.
    kind: str
    applies_to: EffectClass | None = None
    # Who drew this line. Defaults to USER, the more restrictive reading, so that a caller
    # that forgets to say cannot accidentally make a bound negotiable (D-030).
    provenance: ConstraintProvenance = ConstraintProvenance.USER
    max_usd: float | None = None
    allowed_recipients: tuple[str, ...] = ()
    allowed_domains: tuple[str, ...] = ()
    window_start: str | None = None
    window_end: str | None = None
    globs: tuple[str, ...] = ()
    unit: str | None = None
    max_value: float | None = None
    note: str = ""

    def matches(self, effect: Effect) -> bool:
        return self.applies_to is None or self.applies_to == effect.effect_class

    def check(self, effect: Effect, args: dict[str, Any]) -> tuple[bool, str]:
        """(satisfied, human-readable reason). A constraint that does not apply passes."""
        if not self.matches(effect):
            return True, ""
        handler = getattr(self, f"_check_{self.kind}", None)
        if handler is None:
            # An unrecognised constraint kind is a configuration error, and the safe
            # reading of "I do not understand this bound" is that it is not satisfied.
            return False, f"unknown constraint kind {self.kind!r}"
        try:
            return handler(effect, args)
        except Exception as exc:  # the monitor decides; it does not crash
            # **A reference monitor must be total.** Phase 2 wrote every handler against
            # bounds a person had typed, and a person does not write a time window with no
            # timezone next to one that has one. Phase 3 put a *model's* output here, and
            # `_check_time_window` raised TypeError comparing a naive datetime with an aware
            # one — 21 episodes of E-01b died mid-decision rather than reaching a verdict
            # (finding F-15). An exception escaping here is worse than any verdict: the
            # caller decides what it means, and "the guard threw" is not one of ALLOW, ASK
            # or BLOCK.
            #
            # Failing closed matches the branch above it: a bound we cannot evaluate is a
            # bound we cannot say is satisfied. Note this can only ever make a decision more
            # restrictive, so it cannot be used to obtain an ALLOW.
            return False, (
                f"{self.kind} constraint could not be evaluated "
                f"({type(exc).__name__}: {exc}); treating it as unsatisfied"
            )

    # -- individual kinds ---------------------------------------------------

    def _check_budget(self, effect: Effect, args: dict[str, Any]) -> tuple[bool, str]:
        if self.max_usd is None:
            return False, "budget constraint has no max_usd"
        mag = effect.magnitude
        if mag is None or mag.unit != "usd":
            return True, ""
        if mag.value > self.max_usd:
            return False, f"amount {mag.value:.2f} usd exceeds the {self.max_usd:.2f} budget"
        return True, ""

    def _check_magnitude(self, effect: Effect, args: dict[str, Any]) -> tuple[bool, str]:
        if self.unit is None or self.max_value is None:
            return False, "magnitude constraint needs unit and max_value"
        mag = effect.magnitude
        if mag is None or mag.unit != self.unit:
            return True, ""
        if mag.value > self.max_value:
            return False, f"{mag.value:g} {self.unit} exceeds the limit of {self.max_value:g}"
        return True, ""

    def _check_recipient(self, effect: Effect, args: dict[str, Any]) -> tuple[bool, str]:
        actual = recipients_of(effect, args)
        if not actual:
            return True, ""
        allowed = {r.lower() for r in self.allowed_recipients}
        bad = [
            r
            for r in actual
            if r.lower() not in allowed
            and not any(r.lower().endswith("@" + d.lstrip("@").lower()) for d in allowed)
        ]
        if bad:
            return False, f"recipients {bad} are not in the authorized set"
        return True, ""

    def _check_domain(self, effect: Effect, args: dict[str, Any]) -> tuple[bool, str]:
        url = str(args.get("url") or effect.resource_id or "")
        if not url:
            return True, ""
        host = url.split("://", 1)[-1].split("/", 1)[0].lower()
        ok = any(
            host == d.lower() or host.endswith("." + d.lower()) for d in self.allowed_domains
        )
        if ok:
            return True, ""
        return False, f"destination host {host!r} is not in the authorized set"

    def _check_time_window(self, effect: Effect, args: dict[str, Any]) -> tuple[bool, str]:
        stamp = str(args.get("start") or args.get("date") or "")
        if not stamp or self.window_start is None or self.window_end is None:
            return True, ""
        try:
            when = datetime.fromisoformat(stamp)
            lo = datetime.fromisoformat(self.window_start)
            hi = datetime.fromisoformat(self.window_end)
        except ValueError:
            return False, f"could not parse {stamp!r} against the authorized window"
        # A bound written without a timezone and an argument written with one cannot be
        # compared, and Python raises rather than guessing. Nor should we guess: assuming
        # the naive side means UTC would silently widen or narrow the window by hours. The
        # comparison is refused instead, which is the same answer this handler already
        # gives to a stamp it cannot parse. `check()` also catches it as a backstop, but a
        # named reason reads better in an audit log than a caught TypeError (F-15).
        aware = {v.tzinfo is not None for v in (when, lo, hi)}
        if len(aware) > 1:
            return False, (
                f"cannot compare {stamp!r} with the window "
                f"{self.window_start}..{self.window_end}: one carries a timezone and the "
                "other does not"
            )
        if lo <= when <= hi:
            return True, ""
        return False, f"{stamp} falls outside {self.window_start}..{self.window_end}"

    def _check_resource_glob(self, effect: Effect, args: dict[str, Any]) -> tuple[bool, str]:
        target = str(effect.resource_id or args.get("path") or args.get("key") or "")
        if not target:
            return True, ""
        if any(fnmatch.fnmatch(target, g) for g in self.globs):
            return True, ""
        return False, f"resource {target!r} is outside the authorized paths"


def recipients_of(effect: Effect, args: dict[str, Any]) -> list[str]:
    """Normalized recipient list, from the arguments or the effect's resource id."""
    raw = args.get("to")
    if raw is None:
        raw = effect.resource_id or ""
    items = raw if isinstance(raw, list) else str(raw).replace(";", ",").split(",")
    return [str(p).strip() for p in items if str(p).strip()]


# ---------------------------------------------------------------------------
# Grants, declassifications, consent
# ---------------------------------------------------------------------------


class Grant(BaseModel):
    """An effect class the user licensed, and the span that licensed it.

    Storing provenance inside the grant rather than beside it is what makes
    "every authorized effect traces to a USER turn" a structural fact.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    effect_class: EffectClass
    provenance_span: str
    rationale: str = ""


class Declassification(BaseModel):
    """Permission for data above a destination's ceiling to reach it anyway (P3)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    max_confidentiality: Confidentiality
    destination: Destination
    provenance_span: str
    note: str = ""

    def covers(self, conf: Confidentiality, destination: Destination) -> bool:
        return (
            conf.rank() <= self.max_confidentiality.rank()
            and destination.rank() <= self.destination.rank()
        )


class ConsentRecord(BaseModel):
    """A human's answer to an ASK. The only key that opens ``expand_via_consent``.

    The validator is the enforcement point for P1. A ``ConsentRecord`` cannot exist unless
    its label was stamped USER by the runtime at ingestion, and labels are never parsed
    out of content (THREAT_MODEL A4), so no amount of untrusted text claiming to be an
    approval can produce one.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    span_id: str
    label: Label
    approved: bool
    # What the ASK put to the human. Always populated, whatever the answer, because a
    # refusal has to be remembered too — see IntentScope.refusals.
    requested_effects: tuple[EffectClass, ...] = ()
    granted_effects: tuple[EffectClass, ...] = ()
    granted_declassifications: tuple[Declassification, ...] = ()
    # Bounds the human agreed to lift (D-030). Only a COMPILER-provenanced constraint may
    # appear here; ``expand_via_consent`` raises on anything else, so a bound the user
    # stated in their own words cannot be negotiated away by answering a dialog.
    relaxed_constraints: tuple[Constraint, ...] = ()
    answer_text: str = ""

    @model_validator(mode="after")
    def _must_carry_user_authority(self) -> ConsentRecord:
        if self.label.integrity is not Integrity.USER:
            raise ScopeViolation(
                "consent must carry a USER label; got "
                f"{self.label.integrity.value}. Only a human can widen scope (D-007)."
            )
        return self


# ---------------------------------------------------------------------------
# IntentScope
# ---------------------------------------------------------------------------


class ScopeCheck(BaseModel):
    """Why an effect was or was not satisfied by a scope. Feeds the audit log verbatim."""

    model_config = ConfigDict(frozen=True)

    satisfied: bool
    in_scope: bool
    constraint_failures: tuple[str, ...] = ()
    # Failures split by who drew the line (D-030). The combinator treats them differently
    # and the audit log has to show which kind fired, so the split is computed once here
    # rather than re-derived by every consumer.
    user_constraint_failures: tuple[str, ...] = ()
    compiler_constraint_failures: tuple[str, ...] = ()
    reason: str = ""

    @property
    def only_compiler_bounds_failed(self) -> bool:
        """Every bound this effect breached was inferred rather than stated.

        The precise condition for escalating instead of refusing: the effect class is
        licensed, and the only thing standing in the way is a model's guess about its
        limits. If a *user-stated* bound also failed, this is False and the refusal stands.
        """
        return (
            self.in_scope
            and not self.satisfied
            and bool(self.compiler_constraint_failures)
            and not self.user_constraint_failures
        )


class IntentScope(BaseModel):
    """Deny-by-default authority over effect classes, plus bounds and declassifications."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    objective: str = ""
    grants: tuple[Grant, ...] = ()
    constraints: tuple[Constraint, ...] = ()
    declassifications: tuple[Declassification, ...] = ()
    open_questions: tuple[str, ...] = ()
    # Effect classes the user has already declined this episode (D-024). Never a source of
    # authority — it can only make later decisions more restrictive — so recording it here
    # does not weaken the monotonicity invariant, and it is written only by a refusal
    # carrying USER provenance.
    refusals: tuple[EffectClass, ...] = ()
    revision: int = 0

    # -- derived ------------------------------------------------------------

    @property
    def authorized_effects(self) -> frozenset[EffectClass]:
        return frozenset(g.effect_class for g in self.grants)

    def provenance_of(self, effect_class: EffectClass) -> str | None:
        for g in self.grants:
            if g.effect_class == effect_class:
                return g.provenance_span
        return None

    # -- operations ---------------------------------------------------------

    def narrow(
        self,
        *,
        revoke: set[EffectClass] | None = None,
        add_constraints: list[Constraint] | None = None,
        add_open_questions: list[str] | None = None,
    ) -> IntentScope:
        """Reduce authority. Callable by anything, including untrusted observations.

        There is deliberately no parameter here that could add a grant or a
        declassification. Narrowing is safe from any source precisely because the
        signature cannot express widening.
        """
        revoke = revoke or set()
        kept = tuple(g for g in self.grants if g.effect_class not in revoke)
        return self.model_copy(
            update={
                "grants": kept,
                "constraints": self.constraints + tuple(add_constraints or []),
                "open_questions": self.open_questions + tuple(add_open_questions or []),
                "revision": self.revision + 1,
            }
        )

    def expand_via_consent(self, record: ConsentRecord) -> IntentScope:
        """The only widening path (D-007). Requires a USER-labeled consent record.

        A refusal is not a no-op. The answer still counts as the human having considered
        the question, and — D-024 — the refused effect classes are recorded so the same
        question is not put to them again this episode. Without that, an agent that
        re-proposes the same effect one resource at a time spends the entire interruption
        budget re-asking a question already answered, which is both a usability failure
        and a foothold for ASK flooding (THREAT_MODEL A6).
        """
        if record.label.integrity is not Integrity.USER:  # defence in depth
            raise ScopeViolation("consent record does not carry USER authority")
        if not record.approved:
            declined = tuple(
                item
                for item in record.requested_effects
                if item not in self.refusals and item not in self.authorized_effects
            )
            return self.model_copy(
                update={
                    "refusals": self.refusals + declined,
                    "revision": self.revision + 1,
                }
            )
        new_grants = tuple(
            Grant(
                effect_class=item,
                provenance_span=record.span_id,
                rationale="granted by the user in answer to an ASK",
            )
            for item in record.granted_effects
            if item not in self.authorized_effects
        )
        # Lifting an inferred bound (D-030). This is a widening, so it goes through exactly
        # the same door as a grant does — a USER-labeled ConsentRecord — and it is refused
        # outright for any bound the user themselves stated. That asymmetry is the whole
        # point: a model's guess about a limit is negotiable, a person's statement of one is
        # not (THREAT_MODEL family B2).
        stated = [
            c
            for c in record.relaxed_constraints
            if c.provenance is not ConstraintProvenance.COMPILER
        ]
        if stated:
            raise ScopeViolation(
                f"consent tried to lift {len(stated)} user-stated bound(s): "
                f"{[c.kind for c in stated]}. Only an inferred bound may be relaxed (D-030)."
            )
        kept_constraints = tuple(
            c for c in self.constraints if c not in record.relaxed_constraints
        )
        return self.model_copy(
            update={
                "grants": self.grants + new_grants,
                "constraints": kept_constraints,
                "declassifications": self.declassifications
                + tuple(record.granted_declassifications),
                "revision": self.revision + 1,
            }
        )

    # -- checking -----------------------------------------------------------

    def satisfies(self, effect: Effect, args: dict[str, Any] | None = None) -> ScopeCheck:
        """Membership plus constraints. Deny-by-default: absence is denial (D-004)."""
        args = args or {}
        klass = effect.effect_class
        if klass not in self.authorized_effects:
            return ScopeCheck(
                satisfied=False,
                in_scope=False,
                reason=f"{klass} is not in the authorized effect set",
            )
        failures = []
        by_user = []
        by_compiler = []
        for c in self.constraints:
            passed, why = c.check(effect, args)
            if not passed:
                rendered = f"{c.kind}: {why}"
                failures.append(rendered)
                if c.provenance is ConstraintProvenance.COMPILER:
                    by_compiler.append(rendered)
                else:
                    by_user.append(rendered)
        if failures:
            return ScopeCheck(
                satisfied=False,
                in_scope=True,
                constraint_failures=tuple(failures),
                user_constraint_failures=tuple(by_user),
                compiler_constraint_failures=tuple(by_compiler),
                reason="; ".join(failures),
            )
        return ScopeCheck(satisfied=True, in_scope=True, reason=f"{klass} is authorized")

    def permits_flow(self, conf: Confidentiality, destination: Destination) -> tuple[bool, str]:
        """P3: may data at this confidentiality reach this destination?"""
        if not exceeds_permitted(conf, destination):
            return True, f"{conf.value} is within what {destination.value} may observe"
        for d in self.declassifications:
            if d.covers(conf, destination):
                return True, f"declassified by {d.provenance_span}"
        return (
            False,
            f"{conf.value} data would reach {destination.value} with no declassification grant",
        )

    # -- convenience --------------------------------------------------------

    def refused(self, effect_class: EffectClass) -> bool:
        return effect_class in self.refusals

    def digest(self) -> str:
        """Stable one-line summary for the audit log's human-readable column."""
        effects = ", ".join(sorted(str(k) for k in self.authorized_effects)) or "(none)"
        refused = f" refused={len(self.refusals)}" if self.refusals else ""
        return (
            f"r{self.revision} effects={{{effects}}} "
            f"constraints={len(self.constraints)}{refused}"
        )


def scope_from_user_turn(
    objective: str,
    effect_classes: list[EffectClass],
    *,
    span_id: str,
    constraints: list[Constraint] | None = None,
    declassifications: list[Declassification] | None = None,
    open_questions: list[str] | None = None,
) -> IntentScope:
    """Build the initial scope from the user's utterance.

    In Phase 2 the caller is a hand-written gold scope (D-023); in Phase 3 it is the
    intent compiler. Either way every grant is stamped with the id of the USER turn that
    licensed it, so the provenance invariant holds from the first revision.
    """
    return IntentScope(
        objective=objective,
        grants=tuple(
            Grant(effect_class=item, provenance_span=span_id, rationale="stated by the user")
            for item in dict.fromkeys(effect_classes)
        ),
        constraints=tuple(constraints or []),
        declassifications=tuple(declassifications or []),
        open_questions=tuple(open_questions or []),
    )


def ec(verb: str, resource_class: str) -> EffectClass:
    """Terse constructor for scope literals in configs and tests."""
    return EffectClass(verb=Verb(verb), resource_class=ResourceClass(resource_class))
