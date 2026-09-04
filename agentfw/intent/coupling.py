"""E-12: withhold a grant the compiler's own open questions call into doubt.

**The observation this exists to act on.** `IntentScope` has carried `open_questions` since
Phase 2 and nothing in `agentfw/policy/` has ever read one. The compiler emits its doubt and
the firewall discards it. Meanwhile every leaking case in E-11 has the same shape: the
compiler **grants the contested class and raises a question that presupposes the action** —
grants `SEND:PUBLIC_WEB` and asks *"What answers should be submitted…"*, grants
`CREATE:CALENDAR` and asks *"Is the exact duration 1 hour or something else?"* It has settled
*whether* and is asking *how*, which is F-16's sentence, in the arms F-17 and F-19 declared
had fixed it.

So: **a granted effect class that the scope's own open questions refer to is withheld**, and
becomes an open question instead.

**What this is not.** Not a score, not a weighting, not a threshold (D-005). It reads no
scenario id. It runs on the compiler's output *before* the scope is built, so it is outside
the TCB (D-006), and it can only ever remove a grant — it cannot manufacture a permission,
which is the direction D-007 cares about. It is a coupling of two fields one component
already emits.

**Two definitions of "refers to", both registered before either ran** (E-12), so that neither
can be quietly tuned into the other:

* ``r1`` — literal. The question contains the class (``SEND:EMAIL``) or its verb token
  (``SEND``). This is the version F-16 considered and dismissed: *"only 2 of 8 open questions
  even name the verb that was granted."*
* ``r2`` — lexicon. The question contains any surface form of the verb, from ``SURFACE_FORMS``
  below. Every entry is an ordinary inflection or a common synonym of the verb it sits under.
  **None was chosen by looking at what the leaking scopes actually asked**, which is the only
  thing that keeps this from being fitted to its own test set — and the real guard on that is
  E-12's prediction 20, which requires the same table to work on the dev slice.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from agentfw.intent import catalog
from agentfw.intent.compiler import CompiledScope

# fmt: off
SURFACE_FORMS: dict[str, tuple[str, ...]] = {
    "SEND": (
        "send", "sends", "sending", "sent", "submit", "submits", "submitting", "submitted",
        "reply", "replies", "replying", "email", "emails", "emailing", "post", "posts",
        "posting",
    ),
    "CREATE": (
        "create", "creates", "creating", "created", "book", "books", "booking", "booked",
        "schedule", "schedules", "scheduling", "scheduled", "set up", "add", "adds",
        "adding", "draft", "drafts",
    ),
    "DELETE": (
        "delete", "deletes", "deleting", "deleted", "remove", "removes", "removing",
        "removed",
    ),
    "PURCHASE": (
        "pay", "pays", "paying", "paid", "purchase", "purchases", "purchasing",
        "purchased", "charge", "charges", "charging", "charged", "buy", "buys", "buying",
        "bought",
    ),
    "GRANT": (
        "grant", "grants", "granting", "granted", "share", "shares", "sharing", "shared",
        "access",
    ),
    "WRITE": (
        "write", "writes", "writing", "wrote", "update", "updates", "updating", "updated",
        "edit", "edits",
    ),
    "PUBLISH": (
        "publish", "publishes", "publishing", "published", "sign", "signs", "signing",
        "signed",
    ),
    "READ": (
        "read", "reads", "reading", "open", "opens", "opening", "check", "checks",
        "checking", "look",
    ),
    "EXECUTE": (
        "run", "runs", "running", "ran", "execute", "executes", "executing", "executed",
    ),
}
# fmt: on

RULES = ("r1", "r2")


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z]+", text.lower()))


def refers_to(question: str, effect_class: str, rule: str) -> bool:
    """Does this open question call this granted effect class into doubt?"""
    verb = effect_class.split(":", 1)[0].upper()
    lowered = question.lower()
    if effect_class.lower() in lowered or verb.lower() in _words(lowered):
        return True
    if rule == "r1":
        return False
    forms = SURFACE_FORMS.get(verb, ())
    words = _words(lowered)
    return any((f in words) if " " not in f else (f in lowered) for f in forms)


def couple(record: CompiledScope, rule: str) -> CompiledScope:
    """Return the record with doubted grants withheld. Never adds a grant."""
    if rule not in RULES:
        raise ValueError(f"unknown coupling rule {rule!r}; registered: {RULES}")
    questions = [q for q in record.open_questions if str(q).strip()]
    if not questions or not record.effects:
        return record.model_copy(deep=True)

    kept: list[str] = []
    withheld: list[str] = []
    for raw in record.effects:
        klass = catalog.render(catalog.parse(raw))
        if any(refers_to(q, klass, rule) for q in questions):
            withheld.append(klass)
        else:
            kept.append(raw)
    if not withheld:
        return record.model_copy(deep=True)
    return record.model_copy(
        deep=True,
        update={
            "effects": kept,
            "open_questions": list(record.open_questions)
            + [
                f"whether {k} was authorized: the compilation granted it and questioned it "
                f"in the same breath"
                for k in withheld
            ],
        },
    )


def couple_all(records: Iterable[CompiledScope], rule: str) -> list[CompiledScope]:
    return [couple(r, rule) for r in records]


def withheld_count(before: Iterable[CompiledScope], after: Iterable[CompiledScope]) -> int:
    return sum(len(b.effects) - len(a.effects) for b, a in zip(before, after, strict=True))
