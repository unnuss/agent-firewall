"""Consent integrity: the ASK is rendered by the firewall, never by the agent (D-008).

**The attack this exists to stop.** An attacker who cannot obtain an ALLOW from the
reference monitor can still try to obtain one from the human, by arranging for the
approval dialog to say something misleading (THREAT_MODEL A5, arXiv:2606.02668). If the
prompt shown to a person is assembled from the agent's own explanation of what it is
doing, then hijacking the agent hijacks the consent channel too, and the human becomes the
weakest link rather than the backstop.

**The rule, and it is absolute.** Every character of an ASK comes from structured facts
the firewall derived: the tool name, the normalized arguments, the declared effects, the
provenance of the evidence, what granting would add to the scope, and how much of the
interruption budget is left. ``ProposedAction.rationale`` — the model's prose — is never
read by this module. That is P4, and it is a property test rather than a review comment.

**Untrusted argument values still have to be shown**, because a reviewer cannot judge
"send this to that address" without seeing the address. They are shown quoted, truncated,
and labeled with where they came from, so the reviewer reads them as data being quoted at
them rather than as the firewall speaking. A payload that says "the firewall has already
approved this" appears as::

    body = "the firewall has already approved this"   [UNTRUSTED_EMAIL, from email:m-003]

which is a very different thing from the same words rendered as narration.
"""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict

from agentfw.core.effects import describe
from agentfw.core.scope import ConsentRecord, Constraint, IntentScope
from agentfw.core.types import Effect, EffectClass, Integrity, Label, TraceSpan

MAX_VALUE_CHARS = 160
MAX_ARGS_SHOWN = 12


class AskRequest(BaseModel):
    """The structured facts an ASK is built from. No free text enters here."""

    model_config = ConfigDict(frozen=True)

    call_id: str
    step: int
    tool: str
    # (name, value, integrity, origin) per argument. Values are quoted at render time.
    arguments: tuple[tuple[str, str, str, str], ...] = ()
    effects: tuple[Effect, ...] = ()
    would_grant: tuple[str, ...] = ()
    # Bounds the assistant *inferred* that this action breaches, and that approving would
    # lift (D-030). Structured rather than pre-rendered, because the consent record has to
    # name the exact constraints being lifted; the text below is derived from them. They
    # are a different kind of thing from would_grant: not "may it do this at all" but "was
    # this limit ever yours".
    relaxable: tuple[Constraint, ...] = ()
    reason: str = ""  # the combinator's own explanation, itself firewall-derived
    evidence: tuple[tuple[str, str], ...] = ()  # (span id, integrity)
    objective: str = ""
    budget_remaining: int = 0


def _truncate(text: str) -> str:
    if len(text) <= MAX_VALUE_CHARS:
        return text
    return text[:MAX_VALUE_CHARS] + f"... [+{len(text) - MAX_VALUE_CHARS} chars]"


def build_request(
    *,
    call_id: str,
    step: int,
    tool: str,
    args: dict[str, Any],
    effects: tuple[Effect, ...],
    would_grant: tuple[str, ...],
    relaxable: tuple[Constraint, ...] = (),
    reason: str,
    scope: IntentScope,
    evidence_spans: list[TraceSpan],
    budget_remaining: int,
) -> AskRequest:
    """Assemble the facts. Every argument is attributed to the span it came from.

    An argument value that appears verbatim in an untrusted span is labeled with that
    span's integrity; one that does not is AGENT_DERIVED, which is the honest answer — the
    model produced it and we cannot say from where.
    """
    attributed: list[tuple[str, str, str, str]] = []
    for name, value in list(args.items())[:MAX_ARGS_SHOWN]:
        text = str(value)
        source = next(
            (s for s in evidence_spans if len(text.strip()) >= 8 and text.strip() in s.content),
            None,
        )
        integrity = source.label.integrity.value if source else Integrity.AGENT_DERIVED.value
        origin = (source.label.origin or source.id) if source else "the assistant"
        attributed.append((name, _truncate(text), integrity, origin))

    return AskRequest(
        call_id=call_id,
        step=step,
        tool=tool,
        arguments=tuple(attributed),
        effects=effects,
        would_grant=would_grant,
        relaxable=relaxable,
        reason=reason,
        evidence=tuple((s.id, s.label.integrity.value) for s in evidence_spans),
        objective=scope.objective,
        budget_remaining=budget_remaining,
    )


def _describe_constraint(c: Constraint) -> str:
    """Firewall-derived prose for one inferred bound. Enum fields and numbers only.

    ``note`` is the compiler's own text and is the one field here that a model wrote, so it
    is quoted rather than narrated — the same treatment untrusted argument values get, and
    for the same reason (P4).
    """
    bound = [
        f"{k}={v}"
        for k, v in (
            ("max_usd", c.max_usd),
            ("recipients", list(c.allowed_recipients) or None),
            ("domains", list(c.allowed_domains) or None),
            ("from", c.window_start),
            ("to", c.window_end),
            ("paths", list(c.globs) or None),
            ("unit", c.unit),
            ("max", c.max_value),
        )
        if v is not None
    ]
    applies = f" on {c.applies_to}" if c.applies_to else ""
    text = f"{c.kind}{applies}: {', '.join(bound)}"
    if c.note:
        text += f'   [inferred from: "{_truncate(c.note)}"]'
    return text


def render(req: AskRequest) -> str:
    """Deterministic template over the facts. Same request, same text, every time."""
    lines = [
        "APPROVAL REQUIRED",
        "",
        f"The assistant proposes to call `{req.tool}` at step {req.step}.",
        "",
        "This would:",
    ]
    lines += [f"  - {describe(e)}" for e in req.effects]
    lines += ["", "With these arguments (quoted exactly, and labeled by where each came from):"]
    if req.arguments:
        for name, value, integrity, origin in req.arguments:
            lines.append(f'  {name} = "{value}"')
            lines.append(f"      [{integrity}, from {origin}]")
    else:
        lines.append("  (no arguments)")

    lines += ["", "Why you are being asked:", f"  {req.reason}"]
    if req.objective:
        lines += ["", "What you originally asked for:", f'  "{_truncate(req.objective)}"']
    if req.would_grant:
        lines += [
            "",
            "Approving grants the assistant this authority for the rest of the task:",
            *[f"  - {g}" for g in req.would_grant],
        ]
    if req.relaxable:
        lines += [
            "",
            "The assistant inferred these limits from your request. You did not state them",
            "in those words, and approving lifts them:",
            *[f"  - {_describe_constraint(c)}" for c in req.relaxable],
        ]
    if req.evidence:
        shown = ", ".join(f"{sid} ({integrity})" for sid, integrity in req.evidence)
        lines += ["", f"Evidence spans behind these arguments: {shown}"]
    lines += [
        "",
        f"Interruptions left this task: {req.budget_remaining}.",
        "Answer APPROVE or DENY.",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Reviewers
# ---------------------------------------------------------------------------


class Reviewer(Protocol):
    """Whatever answers an ASK. In experiments this is a scripted oracle, never a model."""

    name: str

    def review(self, req: AskRequest, *, licensed: bool | None = None) -> ConsentRecord: ...


class ScriptedReviewer:
    """The evaluation's stand-in for a human (EVALUATION section 5, "reviewer model").

    Answers from ground truth — did the user's utterance in fact license this effect? —
    with a configurable error rate ``epsilon``, so that the effect of imperfect human
    review is measured rather than assumed. THREAT_MODEL 4.7 concedes that we run no
    human-subject study; this is the honest substitute and it is labeled as one.

    Errors are drawn from a seeded RNG keyed by the call id, so a replay of the same
    episode produces the same answers. A reviewer whose mistakes move between runs would
    make every downstream number irreproducible.

    The **fatigue** model — epsilon rising with the number of interruptions already spent,
    which is what reproduces the inverted-U of arXiv:2606.08919 — belongs to Phase 4 with
    the ASK-budget sweep. It is deliberately absent rather than stubbed.
    """

    name = "scripted"

    def __init__(self, *, epsilon: float = 0.0, seed: int = 20260830) -> None:
        if not 0.0 <= epsilon <= 1.0:
            raise ValueError("epsilon must be a probability")
        self.epsilon = epsilon
        self.seed = seed
        self.reviewed: list[tuple[str, bool]] = []

    def _errs(self, call_id: str) -> bool:
        if self.epsilon <= 0.0:
            return False
        import random

        return random.Random(f"{self.seed}:{call_id}").random() < self.epsilon

    def review(self, req: AskRequest, *, licensed: bool | None = None) -> ConsentRecord:
        # ``licensed is None`` means the harness has no ground truth for this action. The
        # conservative reading of "nobody knows whether the user wanted this" is that they
        # did not ask for it, which keeps an unlabeled action from being waved through.
        truth = bool(licensed)
        approved = (not truth) if self._errs(req.call_id) else truth
        self.reviewed.append((req.call_id, approved))
        return ConsentRecord(
            span_id=f"ask:{req.call_id}",
            # A scripted reviewer stands in for the user, so its answer carries USER
            # integrity — assigned here, by trusted harness code, exactly as the runtime
            # assigns the label on a real user turn. Nothing about the request's content
            # influences it.
            label=Label(integrity=Integrity.USER, origin=f"reviewer:{self.name}"),
            approved=approved,
            requested_effects=tuple(_parse_effect_classes(req.would_grant)),
            granted_effects=tuple(_parse_effect_classes(req.would_grant)) if approved else (),
            relaxed_constraints=req.relaxable if approved else (),
            answer_text="APPROVE" if approved else "DENY",
        )


def _parse_effect_classes(rendered: tuple[str, ...]) -> list[EffectClass]:
    """Turn ``(VERB, RESOURCE)`` display strings back into effect classes."""
    from agentfw.core.types import ResourceClass, Verb

    out = []
    for item in rendered:
        verb, _, resource = item.strip("()").partition(",")
        out.append(
            EffectClass(verb=Verb(verb.strip()), resource_class=ResourceClass(resource.strip()))
        )
    return out
