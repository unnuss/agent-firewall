"""Label-lattice properties.

The scope-monotonicity guarantee (P1) rests on integrity never being *raised* by combining
values. That is a property, not an example, so it gets a property test even though the
full label algebra does not land until Phase 2.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from agentfw.core.types import (
    Confidentiality,
    Effect,
    EffectClass,
    Integrity,
    Label,
    ResourceClass,
    Verb,
    meet_all,
)

integrities = st.sampled_from(list(Integrity))
confidentialities = st.sampled_from(list(Confidentiality))
labels = st.builds(Label, integrity=integrities, confidentiality=confidentialities)


@given(labels, labels)
def test_meet_never_raises_integrity(a: Label, b: Label) -> None:
    m = a.meet(b)
    assert m.integrity.rank() <= min(a.integrity.rank(), b.integrity.rank())


@given(labels, labels)
def test_meet_never_lowers_confidentiality(a: Label, b: Label) -> None:
    m = a.meet(b)
    assert m.confidentiality.rank() >= max(a.confidentiality.rank(), b.confidentiality.rank())


@given(labels, labels)
def test_meet_is_commutative_on_levels(a: Label, b: Label) -> None:
    left, right = a.meet(b), b.meet(a)
    assert left.integrity.rank() == right.integrity.rank()
    assert left.confidentiality == right.confidentiality


@given(labels, labels, labels)
def test_meet_is_associative_on_levels(a: Label, b: Label, c: Label) -> None:
    left = a.meet(b).meet(c)
    right = a.meet(b.meet(c))
    assert left.integrity.rank() == right.integrity.rank()
    assert left.confidentiality == right.confidentiality


@given(labels)
def test_meet_is_idempotent(a: Label) -> None:
    assert a.meet(a).integrity == a.integrity
    assert a.meet(a).confidentiality == a.confidentiality


@given(st.lists(labels, min_size=1, max_size=8))
def test_meet_all_matches_worst_case(items: list[Label]) -> None:
    m = meet_all(items)
    assert m.integrity.rank() == min(i.integrity.rank() for i in items)
    assert m.confidentiality.rank() == max(i.confidentiality.rank() for i in items)


def test_untrusted_content_ranks_below_agent_derived() -> None:
    for kind in (
        Integrity.UNTRUSTED_WEB,
        Integrity.UNTRUSTED_EMAIL,
        Integrity.UNTRUSTED_DOC,
        Integrity.UNTRUSTED_TOOL,
    ):
        assert kind.is_untrusted
        assert kind.rank() < Integrity.AGENT_DERIVED.rank()
    assert not Integrity.USER.is_untrusted
    assert not Integrity.AGENT_DERIVED.is_untrusted


def test_effect_class_is_hashable_and_derived() -> None:
    e = Effect(verb=Verb.SEND, resource_class=ResourceClass.EMAIL)
    assert e.effect_class == EffectClass(verb=Verb.SEND, resource_class=ResourceClass.EMAIL)
    assert len({e.effect_class, e.effect_class}) == 1
