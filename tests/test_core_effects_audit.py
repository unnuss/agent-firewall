"""The effect mapper's fail-closed contract, and the audit chain's tamper evidence.

Two small modules, one test file, because the properties they carry are short:

* an unmappable call must be distinguishable from a call with no effects, or
  deny-by-default authorizes it vacuously (``core/effects``);
* altering a logged event must invalidate the chain (``core/audit``).
"""

from __future__ import annotations

import json

import pytest
from hypothesis import given
from hypothesis import strategies as st

from agentfw.core.audit import GENESIS, AuditLog, summarise
from agentfw.core.effects import EffectMapper, consequential, describe
from agentfw.core.scope import ec, scope_from_user_turn
from agentfw.core.types import (
    Effect,
    Externality,
    Integrity,
    Label,
    Magnitude,
    ProposedAction,
    ResourceClass,
    Reversibility,
    Verb,
    Verdict,
)
from agentfw.sandbox.registry import ToolRouter, load_all
from agentfw.sandbox.world import World

AGENT = Label(integrity=Integrity.AGENT_DERIVED)


def act(tool: str, args: dict, step: int = 1) -> ProposedAction:
    return ProposedAction(
        call_id=f"c{step}", step=step, tool_name=tool, args=args, arg_label=AGENT
    )


# ---------------------------------------------------------------------------
# The mapper
# ---------------------------------------------------------------------------


def test_mapper_reports_failure_rather_than_an_empty_effect_list():
    """The fail-open path this module exists to close.

    Under deny-by-default an empty effect list means "nothing to authorize", so a mapper
    that returned ``[]`` on an unknown tool would let it through the membership check.
    """
    mapper = EffectMapper(lambda tool, args: (_ for _ in ()).throw(KeyError(tool)))
    mapping = mapper.map(act("no_such_tool", {}))
    assert not mapping.ok
    assert mapping.effects == ()
    assert "no_such_tool" in mapping.reason


def test_mapper_treats_an_empty_declaration_as_a_failure_not_a_permission():
    mapper = EffectMapper(lambda tool, args: [])
    mapping = mapper.map(act("silent_tool", {}))
    assert not mapping.ok


def test_mapper_passes_real_declarations_through():
    load_all()
    world = World.from_fixture("office_baseline")
    router = ToolRouter.for_tools(world, ["email_send"])
    mapper = EffectMapper(router.declare_for)
    mapping = mapper.map(act("email_send", {"to": "a@b.example", "subject": "s", "body": "b"}))
    assert mapping.ok
    assert mapping.classes == {ec("SEND", "EMAIL")}


def test_router_declare_for_raises_where_declare_swallows():
    load_all()
    world = World.from_fixture("office_baseline")
    router = ToolRouter.for_tools(world, ["email_send"])
    assert router.declare(act("nope", {})) == []
    with pytest.raises(KeyError):
        router.declare_for("nope", {})


# ---------------------------------------------------------------------------
# consequential() is structural, not a score
# ---------------------------------------------------------------------------


@given(
    st.sampled_from(list(Reversibility)),
    st.sampled_from(list(Externality)),
    st.floats(min_value=0, max_value=1e9, allow_nan=False),
)
def test_consequential_ignores_magnitude_entirely(
    rev: Reversibility, ext: Externality, amount: float
):
    """Magnitude belongs to Phase 4's cost model, not to a Phase 2 predicate (D-005).

    If magnitude leaked into this predicate it would be a threshold, and a threshold is
    the tuned risk score the project decided against.
    """
    base = Effect(
        verb=Verb.SEND, resource_class=ResourceClass.EMAIL, reversibility=rev, externality=ext
    )
    with_magnitude = base.model_copy(update={"magnitude": Magnitude(unit="usd", value=amount)})
    assert consequential(base) == consequential(with_magnitude)


def test_a_draft_is_not_consequential_and_a_send_is():
    draft = Effect(verb=Verb.CREATE, resource_class=ResourceClass.EMAIL)
    send = Effect(
        verb=Verb.SEND,
        resource_class=ResourceClass.EMAIL,
        reversibility=Reversibility.IRREVERSIBLE,
        externality=Externality.VISIBLE_TO_THIRD_PARTY,
    )
    assert not consequential(draft)
    assert consequential(send)


def test_describe_uses_only_declared_fields():
    effect = Effect(
        verb=Verb.PURCHASE,
        resource_class=ResourceClass.FINANCIAL,
        reversibility=Reversibility.IRREVERSIBLE,
        externality=Externality.BINDING_ON_USER,
        magnitude=Magnitude(unit="usd", value=214.0),
        resource_id="Cloudhost",
    )
    text = describe(effect)
    assert "214.00 usd" in text and "irreversible" in text and "Cloudhost" in text


# ---------------------------------------------------------------------------
# The audit chain
# ---------------------------------------------------------------------------


def _event(log: AuditLog, tool: str, verdict: Verdict = Verdict.ALLOW):
    scope = scope_from_user_turn("o", [ec("READ", "EMAIL")], span_id="s002")
    return log.append(
        call_id=f"c{len(log)}",
        step=1,
        tool=tool,
        args={"folder": "inbox"},
        arg_integrity=Integrity.USER.value,
        arg_confidentiality="PUBLIC",
        scope=scope,
        scope_digest=scope.digest(),
        policy_verdict=verdict,
        verdict=verdict,
        decided_by="test",
        explanation="because",
    )


def test_chain_links_and_verifies():
    log = AuditLog("ep-1")
    first = _event(log, "email_list")
    second = _event(log, "email_read")
    assert first.prev_hash == GENESIS
    assert second.prev_hash == first.hash
    assert log.verify() == (True, "2 events, chain intact")


def test_altering_a_logged_event_breaks_the_chain():
    log = AuditLog("ep-1")
    _event(log, "email_list")
    _event(log, "payments_charge", verdict=Verdict.BLOCK)
    _event(log, "email_read")
    # An attacker rewrites a BLOCK into an ALLOW after the fact.
    log.events[1] = log.events[1].model_copy(update={"verdict": Verdict.ALLOW})
    intact, reason = log.verify()
    assert not intact
    assert "altered after logging" in reason


def test_dropping_an_event_breaks_the_chain():
    log = AuditLog("ep-1")
    for name in ("email_list", "payments_charge", "email_read"):
        _event(log, name)
    del log.events[1]
    log.events[1] = log.events[1].model_copy(update={"seq": 1})
    intact, reason = log.verify()
    assert not intact
    assert "chains to" in reason


def test_round_trips_through_jsonl(tmp_path):
    log = AuditLog("ep-1")
    _event(log, "email_list")
    _event(log, "email_read")
    path = log.write(tmp_path / "audit.jsonl")
    reloaded = AuditLog.load(path)
    assert reloaded.verify()[0]
    assert [e.hash for e in reloaded.events] == [e.hash for e in log.events]
    assert reloaded.episode_id == "ep-1"


def test_replay_reports_only_the_events_that_disagree():
    log = AuditLog("ep-1")
    _event(log, "email_list")
    _event(log, "payments_charge")
    # A policy that now blocks everything disagrees with both logged ALLOWs.
    mismatches = log.replay(lambda event: Verdict.BLOCK)
    assert [m["seq"] for m in mismatches] == [0, 1]
    assert log.replay(lambda event: event.policy_verdict) == []


def test_summary_counts_interruptions_not_pending_verdicts():
    """An approved ASK is logged as ALLOW; the interruption still has to be counted."""
    log = AuditLog("ep-1")
    scope = scope_from_user_turn("o", [ec("READ", "EMAIL")], span_id="s002")
    log.append(
        call_id="c1",
        step=1,
        tool="email_send",
        args={},
        arg_integrity="USER",
        arg_confidentiality="PUBLIC",
        scope=scope,
        scope_digest=scope.digest(),
        policy_verdict=Verdict.ASK,
        verdict=Verdict.ALLOW,
        decided_by="placeholder+consent",
        explanation="approved",
        ask_text="APPROVAL REQUIRED ...",
        consent_approved=True,
    )
    summary = summarise(log)
    assert summary.allow == 1
    assert summary.asks_raised == 1
    assert summary.asks_approved == 1


def test_event_payload_excludes_its_own_hash():
    log = AuditLog("ep-1")
    event = _event(log, "email_list")
    assert "hash" not in event.payload()
    assert json.loads(event.model_dump_json())["hash"] == event.hash
