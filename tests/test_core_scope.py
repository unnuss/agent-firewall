"""P1 — scope monotonicity, as a property rather than a set of examples.

    **P1.** No sequence of untrusted content can add an effect class to the IntentScope.

Examples cannot establish this; the claim quantifies over *all* operation sequences, which
is what hypothesis is for. The tests below generate arbitrary sequences of scope
operations from arbitrary label sources and assert that authority never grows except
through a USER-labeled consent record.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from agentfw.core.labels import Destination
from agentfw.core.scope import (
    ConsentRecord,
    Constraint,
    Declassification,
    IntentScope,
    ScopeViolation,
    ec,
    scope_from_user_turn,
)
from agentfw.core.types import (
    Confidentiality,
    Effect,
    EffectClass,
    Externality,
    Integrity,
    Label,
    Magnitude,
    ResourceClass,
    Reversibility,
    Verb,
)

verbs = st.sampled_from(list(Verb))
resources = st.sampled_from(list(ResourceClass))
effect_classes = st.builds(EffectClass, verb=verbs, resource_class=resources)
non_user_integrity = st.sampled_from([i for i in Integrity if i is not Integrity.USER])


def _scope(classes: list[EffectClass]) -> IntentScope:
    return scope_from_user_turn("objective", classes, span_id="s002")


# ---------------------------------------------------------------------------
# P1
# ---------------------------------------------------------------------------


@given(st.lists(effect_classes, max_size=6), st.lists(effect_classes, max_size=6))
def test_narrow_never_grows_authority(start: list[EffectClass], revoke: list[EffectClass]):
    scope = _scope(start)
    before = scope.authorized_effects
    after = scope.narrow(revoke=set(revoke)).authorized_effects
    assert after <= before


@given(st.lists(effect_classes, max_size=6), st.lists(st.text(max_size=40), max_size=4))
def test_narrow_by_adding_constraints_never_grows_authority(
    start: list[EffectClass], questions: list[str]
):
    scope = _scope(start)
    tightened = scope.narrow(
        add_constraints=[Constraint(kind="budget", max_usd=1.0)],
        add_open_questions=questions,
    )
    assert tightened.authorized_effects == scope.authorized_effects
    # and a bound that was added can only ever refuse more, never fewer, purchases
    purchase = Effect(
        verb=Verb.PURCHASE,
        resource_class=ResourceClass.FINANCIAL,
        magnitude=Magnitude(unit="usd", value=500.0),
    )
    if EffectClass(verb=Verb.PURCHASE, resource_class=ResourceClass.FINANCIAL) in start:
        assert scope.satisfies(purchase).satisfied
        assert not tightened.satisfies(purchase).satisfied


@given(non_user_integrity, st.lists(effect_classes, min_size=1, max_size=4))
def test_untrusted_content_cannot_construct_consent(
    integrity: Integrity, wanted: list[EffectClass]
):
    """The enforcement point for P1: a non-USER label cannot become a ConsentRecord.

    Note the shape of the assertion. It is not "the scope refuses the record" — the record
    cannot be *built*, so there is nothing for a caller to forget to check.
    """
    with pytest.raises(ScopeViolation):
        ConsentRecord(
            span_id="s099",
            label=Label(integrity=integrity, origin="an attacker-controlled page"),
            approved=True,
            granted_effects=tuple(wanted),
        )


@settings(max_examples=200)
@given(
    st.lists(effect_classes, max_size=4),
    st.lists(
        st.tuples(non_user_integrity, st.lists(effect_classes, max_size=3)),
        max_size=8,
    ),
)
def test_no_sequence_of_untrusted_operations_widens_scope(
    start: list[EffectClass],
    attempts: list[tuple[Integrity, list[EffectClass]]],
):
    """The full P1 statement: arbitrary untrusted operation sequences never add authority."""
    scope = _scope(start)
    baseline = scope.authorized_effects
    for integrity, wanted in attempts:
        # Everything an attacker can actually reach: narrowing (allowed from any source)
        # and attempting to forge consent (refused at construction).
        scope = scope.narrow(add_open_questions=["injected"])
        try:
            record = ConsentRecord(
                span_id="forged",
                label=Label(integrity=integrity),
                approved=True,
                granted_effects=tuple(wanted),
            )
        except ScopeViolation:
            continue
        scope = scope.expand_via_consent(record)  # pragma: no cover - unreachable
    assert scope.authorized_effects <= baseline


@given(st.lists(effect_classes, max_size=4), st.lists(effect_classes, min_size=1, max_size=4))
def test_user_consent_is_the_only_widening_path(
    start: list[EffectClass], granted: list[EffectClass]
):
    scope = _scope(start)
    record = ConsentRecord(
        span_id="ask:c1",
        label=Label(integrity=Integrity.USER, origin="user"),
        approved=True,
        granted_effects=tuple(granted),
    )
    widened = scope.expand_via_consent(record)
    assert widened.authorized_effects == scope.authorized_effects | set(granted)
    # and every newly authorized class traces back to the turn that licensed it
    for item in granted:
        assert widened.provenance_of(item) is not None


def test_refused_consent_grants_nothing_but_remembers_the_answer():
    """D-024: a refusal narrows, and narrowing is always allowed."""
    scope = _scope([ec("READ", "EMAIL")])
    record = ConsentRecord(
        span_id="ask:c1",
        label=Label(integrity=Integrity.USER),
        approved=False,
        requested_effects=(ec("SEND", "EMAIL"),),
    )
    after = scope.expand_via_consent(record)
    assert after.authorized_effects == scope.authorized_effects
    assert after.revision == scope.revision + 1
    assert after.refused(ec("SEND", "EMAIL"))


@given(st.lists(effect_classes, max_size=4), st.lists(effect_classes, min_size=1, max_size=4))
def test_a_refusal_never_adds_authority(start: list[EffectClass], asked: list[EffectClass]):
    scope = _scope(start)
    refused = scope.expand_via_consent(
        ConsentRecord(
            span_id="ask:c1",
            label=Label(integrity=Integrity.USER),
            approved=False,
            requested_effects=tuple(asked),
        )
    )
    assert refused.authorized_effects == scope.authorized_effects
    # and nothing already authorized is ever recorded as refused, which would make the
    # scope contradict itself
    assert not set(refused.refusals) & refused.authorized_effects


def test_every_authorized_effect_carries_provenance():
    scope = _scope([ec("READ", "EMAIL"), ec("CREATE", "EMAIL")])
    assert all(g.provenance_span for g in scope.grants)
    assert scope.authorized_effects == {g.effect_class for g in scope.grants}


def test_scope_is_frozen():
    scope = _scope([ec("READ", "EMAIL")])
    with pytest.raises(ValidationError):
        scope.grants = ()


# ---------------------------------------------------------------------------
# Deny-by-default and constraints (D-004, threat family B2)
# ---------------------------------------------------------------------------


def test_absent_effect_class_is_denied():
    scope = _scope([ec("READ", "EMAIL")])
    check = scope.satisfies(Effect(verb=Verb.SEND, resource_class=ResourceClass.EMAIL))
    assert not check.satisfied and not check.in_scope


def test_budget_constraint_rejects_an_over_limit_purchase():
    scope = scope_from_user_turn(
        "pay the invoice, up to 100 dollars",
        [ec("PURCHASE", "FINANCIAL")],
        span_id="s002",
        constraints=[Constraint(kind="budget", max_usd=100.0)],
    )
    under = Effect(
        verb=Verb.PURCHASE,
        resource_class=ResourceClass.FINANCIAL,
        magnitude=Magnitude(unit="usd", value=64.0),
    )
    over = under.model_copy(update={"magnitude": Magnitude(unit="usd", value=214.0)})
    assert scope.satisfies(under).satisfied
    breach = scope.satisfies(over)
    assert not breach.satisfied and breach.in_scope  # right class, wrong instance
    assert "exceeds" in breach.reason


def test_recipient_constraint_accepts_a_domain_and_rejects_a_stranger():
    scope = scope_from_user_turn(
        "reply to Sam",
        [ec("SEND", "EMAIL")],
        span_id="s002",
        constraints=[
            Constraint(kind="recipient", allowed_recipients=("northwind-systems.com",))
        ],
    )
    effect = Effect(verb=Verb.SEND, resource_class=ResourceClass.EMAIL)
    assert scope.satisfies(effect, {"to": "sam.okafor@northwind-systems.com"}).satisfied
    assert not scope.satisfies(effect, {"to": "attacker@evil.example"}).satisfied


def test_resource_glob_constraint_bounds_deletion():
    scope = scope_from_user_turn(
        "clean up the export folder",
        [ec("DELETE", "USER_FILES")],
        span_id="s002",
        constraints=[Constraint(kind="resource_glob", globs=("archive/exports/*",))],
    )
    effect = Effect(verb=Verb.DELETE, resource_class=ResourceClass.USER_FILES)
    assert scope.satisfies(effect, {"path": "archive/exports/tmp-1.csv"}).satisfied
    assert not scope.satisfies(effect, {"path": "reports/q4-2025-final.md"}).satisfied


def test_an_unrecognised_constraint_kind_fails_closed():
    scope = scope_from_user_turn(
        "do a thing",
        [ec("SEND", "EMAIL")],
        span_id="s002",
        constraints=[Constraint(kind="vibes")],
    )
    send = Effect(verb=Verb.SEND, resource_class=ResourceClass.EMAIL)
    assert not scope.satisfies(send).satisfied


# ---------------------------------------------------------------------------
# P3 at the scope level
# ---------------------------------------------------------------------------


def test_secret_data_needs_a_declassification_to_leave():
    scope = _scope([ec("SEND", "EMAIL")])
    ok, _ = scope.permits_flow(Confidentiality.SECRET, Destination.THIRD_PARTY)
    assert not ok
    granted = scope_from_user_turn(
        "send the keys to ops",
        [ec("SEND", "EMAIL")],
        span_id="s002",
        declassifications=[
            Declassification(
                max_confidentiality=Confidentiality.SECRET,
                destination=Destination.THIRD_PARTY,
                provenance_span="s002",
            )
        ],
    )
    allowed, reason = granted.permits_flow(Confidentiality.SECRET, Destination.THIRD_PARTY)
    assert allowed and "s002" in reason


def test_private_correspondence_needs_no_grant_but_public_posting_does():
    scope = _scope([ec("SEND", "EMAIL")])
    assert scope.permits_flow(Confidentiality.PRIVATE, Destination.THIRD_PARTY)[0]
    assert not scope.permits_flow(Confidentiality.PRIVATE, Destination.PUBLIC)[0]


def test_declassification_does_not_cover_a_wider_destination():
    scope = scope_from_user_turn(
        "share with the client",
        [ec("SEND", "EMAIL")],
        span_id="s002",
        declassifications=[
            Declassification(
                max_confidentiality=Confidentiality.PRIVATE,
                destination=Destination.THIRD_PARTY,
                provenance_span="s002",
            )
        ],
    )
    assert scope.permits_flow(Confidentiality.PRIVATE, Destination.THIRD_PARTY)[0]
    assert not scope.permits_flow(Confidentiality.PRIVATE, Destination.PUBLIC)[0]
    assert not scope.permits_flow(Confidentiality.SECRET, Destination.THIRD_PARTY)[0]


def test_effect_with_binding_externality_is_never_local():
    from agentfw.core.labels import destination_of

    binding = Effect(
        verb=Verb.PURCHASE,
        resource_class=ResourceClass.FINANCIAL,
        reversibility=Reversibility.IRREVERSIBLE,
        externality=Externality.BINDING_ON_USER,
    )
    assert destination_of(binding) is not Destination.LOCAL
