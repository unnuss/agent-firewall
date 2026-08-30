"""Label algebra and the destination lattice.

``types.py`` defines the two lattices and the pairwise ``meet``. This module holds the
operations the firewall performs *over* them, which are of two kinds:

1. **Propagation** — combining the labels of many trace spans into the label of a derived
   value. Sound direction: integrity may only fall, confidentiality may only rise.
2. **Destination classification** — an effect does not only touch a resource, it exposes
   the data it carries to an audience. ``destination_of`` says who that is, and
   ``permits`` says the most restricted confidentiality that audience may observe without
   an explicit declassification grant. Together they are what makes P3 checkable.

TCB code (ARCHITECTURE section 2): deterministic, no network, no model calls. Nothing here
reads content — only labels, verbs and externality, all of which were stamped by the
runtime.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from agentfw.core.types import (
    Confidentiality,
    Effect,
    Externality,
    Integrity,
    Label,
    ResourceClass,
    TraceSpan,
    Verb,
    meet_all,
)

# ---------------------------------------------------------------------------
# Propagation
# ---------------------------------------------------------------------------


def propagate(labels: list[Label]) -> Label:
    """Label of a value derived from several sources: meet integrity, join confidentiality.

    Thin alias for ``meet_all`` so that call sites in the monitors read as what they mean.
    An empty list yields AGENT_DERIVED/PUBLIC — the label of a value the model invented,
    which carries no authority and reveals nothing.
    """
    return meet_all(labels)


def is_untrusted(label: Label) -> bool:
    return label.integrity.is_untrusted


def all_untrusted(labels: list[Label]) -> bool:
    """True only if there is at least one label and every one of them is untrusted.

    The emptiness check matters: "no evidence" must not read as "all evidence is
    untrusted", or an action with no traceable support would be denied for the wrong
    reason.
    """
    return bool(labels) and all(lab.integrity.is_untrusted for lab in labels)


def any_user_authority(labels: list[Label]) -> bool:
    """Does any of these labels carry user or system authority?"""
    return any(lab.integrity in (Integrity.USER, Integrity.SYSTEM) for lab in labels)


def confidentiality_of(labels: list[Label]) -> Confidentiality:
    if not labels:
        return Confidentiality.PUBLIC
    return max((lab.confidentiality for lab in labels), key=lambda c: c.rank())


# ---------------------------------------------------------------------------
# Destinations
# ---------------------------------------------------------------------------


class Destination(StrEnum):
    """Who can observe the data an effect carries.

    Deliberately coarse. A finer taxonomy (this recipient vs that recipient) belongs in
    constraints, which are per-scope and checkable, not in a global lattice.
    """

    LOCAL = "LOCAL"  # stays inside the user's own account
    THIRD_PARTY = "THIRD_PARTY"  # a named external party sees it
    PUBLIC = "PUBLIC"  # anyone can see it

    def rank(self) -> int:
        return {"LOCAL": 0, "THIRD_PARTY": 1, "PUBLIC": 2}[self.value]


# Verbs that move data outward. READ pulls data in; it cannot leak by itself.
_OUTBOUND_VERBS = frozenset({Verb.SEND, Verb.PUBLISH, Verb.GRANT, Verb.PURCHASE})


def destination_of(effect: Effect) -> Destination:
    """Where the data in this effect's arguments ends up.

    Derived from the effect's own externality, which the tool declared, rather than from
    the tool name — two tools that both mail a file must classify identically (D-003).
    """
    if effect.externality is Externality.NONE and effect.verb not in _OUTBOUND_VERBS:
        return Destination.LOCAL
    if effect.resource_class is ResourceClass.PUBLIC_WEB and effect.verb in _OUTBOUND_VERBS:
        return Destination.PUBLIC
    if effect.verb is Verb.GRANT:
        # A share grant's audience is the principal it names; ``anyone`` is public and is
        # distinguished by magnitude, which the storage tools already set.
        if effect.magnitude is not None and effect.magnitude.value >= _ANYONE_THRESHOLD:
            return Destination.PUBLIC
        return Destination.THIRD_PARTY
    if effect.externality is Externality.NONE:
        return Destination.LOCAL
    return Destination.THIRD_PARTY


# storage_share/files_share_link encode "anyone with the link" as a large principal count.
_ANYONE_THRESHOLD = 1000.0


def permits(destination: Destination) -> Confidentiality:
    """Most restricted confidentiality this destination may observe without a grant.

    LOCAL may see anything: the data never leaves the user. THIRD_PARTY may see PRIVATE
    material — ordinary correspondence is exactly that — but not SECRET. PUBLIC may see
    only PUBLIC. Declassification grants (core/scope.py) are the only way past this, and
    each one traces to a USER turn (P3).
    """
    return {
        Destination.LOCAL: Confidentiality.SECRET,
        Destination.THIRD_PARTY: Confidentiality.PRIVATE,
        Destination.PUBLIC: Confidentiality.PUBLIC,
    }[destination]


def exceeds_permitted(conf: Confidentiality, destination: Destination) -> bool:
    return conf.rank() > permits(destination).rank()


# ---------------------------------------------------------------------------
# Literal-evidence provenance
# ---------------------------------------------------------------------------

# Below this length an argument value collides with unrelated text too often to count as
# evidence. Kept identical to agent.trace.MIN_EVIDENCE_LEN on purpose: the two must agree
# or the audit log's evidence spans will not match the monitor's.
MIN_EVIDENCE_LEN = 8


def _needles(args: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for value in args.values():
        text = str(value).strip()
        if len(text) >= MIN_EVIDENCE_LEN:
            out.append(text)
    return out


def evidence_spans(args: dict[str, Any], spans: list[TraceSpan]) -> list[TraceSpan]:
    """Spans whose content contains an argument value verbatim.

    **Under-approximates influence and is meant to.** A value the model paraphrased leaves
    no literal trace, so absence of evidence here is not evidence of independence. That is
    why this is only ever used to *deny* (an out-of-scope action whose every literal
    support is untrusted) and never to grant. Sharpening it is Phase 3's dependency
    screener, and the gap is RISK R-03's real motivation.
    """
    needles = _needles(args)
    if not needles:
        return []
    return [s for s in spans if any(n in s.content for n in needles)]


def carried_confidentiality(args: dict[str, Any], spans: list[TraceSpan]) -> Confidentiality:
    """Confidentiality of the data literally present in these arguments.

    Precise rather than conservative, and that is the right choice *for this question*:
    P3 is a claim about values that actually reach an argument, so literal containment is
    the exact test. The conservative context label answers a different question (could the
    model have been influenced?) and is recorded separately as advisory evidence.
    """
    return confidentiality_of([s.label for s in evidence_spans(args, spans)])
