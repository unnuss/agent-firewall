"""The append-only, hash-chained audit log, and offline decision replay.

Two requirements shape this module, and they pull in the same direction.

**Tamper evidence.** THREAT_MODEL section 2 grants the attacker everything except the
ability to modify our code or the audit log. The chain is what makes the second half
enforceable rather than assumed: each event's hash covers the previous event's hash, so
altering or dropping any event invalidates every hash after it. This does not *prevent*
tampering — an attacker who can rewrite the file can rewrite the chain — it makes silent
tampering impossible for anyone who cannot rewrite the whole tail, which is the honest
guarantee and the one worth claiming.

**Replayability.** ARCHITECTURE section 8 requires that a decision can be re-derived
offline without re-running the LLM, because that is what separates a dashboard that
*explains* decisions from one that *animates* them (CLAUDE.md failure mode 6). So an event
stores the complete decision input — the scope as it stood, the mapped effects, every
monitor signal — and not merely the verdict. ``replay`` re-runs the combinator over that
input and reports any event whose verdict does not reproduce.

The size cost of storing whole scope snapshots is real and accepted: a scope is a few
hundred bytes, and a log that cannot reproduce its own decisions is not worth keeping.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from agentfw.core.scope import IntentScope
from agentfw.core.types import Effect, Verdict

GENESIS = "0" * 64


class AuditEvent(BaseModel):
    """One proposed action and everything that decided its fate."""

    model_config = ConfigDict(frozen=True)

    seq: int
    episode_id: str
    call_id: str
    step: int

    # -- what was proposed --------------------------------------------------
    tool: str
    args: dict[str, Any]
    arg_integrity: str
    arg_confidentiality: str
    evidence_spans: tuple[str, ...] = ()

    # -- what it would do ---------------------------------------------------
    effects: tuple[Effect, ...] = ()
    mapping_ok: bool = True
    mapping_reason: str = ""

    # -- what the monitor knew ----------------------------------------------
    scope: IntentScope
    scope_digest: str
    signals: tuple[dict[str, Any], ...] = ()
    gates_fired: tuple[str, ...] = ()

    # -- what it decided ----------------------------------------------------
    # ``policy_verdict`` is what the combinator returned from the inputs above; it is what
    # ``replay`` reproduces. ``verdict`` is the outcome after the consent step, which is
    # not a function of those inputs — it depends on what a human said. Recording only one
    # number would make the log either unreplayable or untrue about what happened.
    policy_verdict: Verdict
    verdict: Verdict
    decided_by: str
    explanation: str
    ask_text: str | None = None
    consent_approved: bool | None = None
    ask_budget_remaining: int = 0
    # Scope revision after any consent was applied. The ``scope`` field above is the scope
    # the policy decided against, which is the one a replay needs.
    scope_revision_after: int = 0

    # -- chain --------------------------------------------------------------
    prev_hash: str = GENESIS
    hash: str = ""

    def payload(self) -> dict[str, Any]:
        """Everything the hash covers: the event minus the hash field itself."""
        data = self.model_dump(mode="json")
        data.pop("hash", None)
        return data

    def compute_hash(self) -> str:
        blob = json.dumps(self.payload(), sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class AuditLog:
    """Append-only in memory, serialisable to JSONL, verifiable offline."""

    def __init__(self, episode_id: str = "") -> None:
        self.episode_id = episode_id
        self.events: list[AuditEvent] = []

    def __len__(self) -> int:
        return len(self.events)

    @property
    def head(self) -> str:
        return self.events[-1].hash if self.events else GENESIS

    def append(self, **fields: Any) -> AuditEvent:
        event = AuditEvent(
            seq=len(self.events),
            episode_id=fields.pop("episode_id", self.episode_id),
            prev_hash=self.head,
            **fields,
        )
        event = event.model_copy(update={"hash": event.compute_hash()})
        self.events.append(event)
        return event

    # -- integrity ----------------------------------------------------------

    def verify(self) -> tuple[bool, str]:
        """Recompute the whole chain. Returns (intact, reason)."""
        prev = GENESIS
        for i, event in enumerate(self.events):
            if event.seq != i:
                return False, f"event {i} carries seq {event.seq}"
            if event.prev_hash != prev:
                return False, (
                    f"event {i} chains to {event.prev_hash[:12]}, expected {prev[:12]}"
                )
            recomputed = event.compute_hash()
            if recomputed != event.hash:
                return False, f"event {i} hash mismatch: content was altered after logging"
            prev = event.hash
        return True, f"{len(self.events)} events, chain intact"

    # -- persistence --------------------------------------------------------

    def to_jsonl(self) -> str:
        return "\n".join(e.model_dump_json() for e in self.events)

    def write(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_jsonl() + "\n", encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: Path) -> AuditLog:
        log = cls()
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                log.events.append(AuditEvent(**json.loads(line)))
        if log.events:
            log.episode_id = log.events[0].episode_id
        return log

    # -- replay -------------------------------------------------------------

    def replay(self, decide: Callable[[AuditEvent], Verdict]) -> list[dict[str, Any]]:
        """Re-derive every verdict from the recorded inputs; report disagreements.

        ``decide`` receives the event and returns the verdict the combinator produces from
        it *now*. A non-empty result means either the log was altered or the policy changed
        since it was written — both worth knowing, and the caller is told which events
        differ rather than merely that something did.

        It is compared against ``policy_verdict``, not ``verdict``. The final verdict on an
        ASK depends on the human's answer, which is not recoverable from the decision
        inputs and is recorded separately in ``consent_approved``. Comparing against it
        would make every answered ASK look like a replay failure.
        """
        out = []
        for event in self.events:
            got = decide(event)
            if got is not event.policy_verdict:
                out.append(
                    {
                        "seq": event.seq,
                        "call_id": event.call_id,
                        "tool": event.tool,
                        "logged": event.policy_verdict.value,
                        "replayed": got.value,
                    }
                )
        return out


class AuditSummary(BaseModel):
    """Per-episode counts, for the evaluation harness.

    ``verdict`` on an event is the *final* outcome, so an ASK the user approved is logged
    as ALLOW. Interruptions are therefore counted from ``ask_text``, not from the verdict:
    the human's attention was spent either way, and attention spent is the quantity the
    whole evaluation is about.
    """

    episode_id: str
    events: int = 0
    allow: int = 0
    ask_pending: int = 0
    block: int = 0
    asks_raised: int = 0
    asks_approved: int = 0
    asks_refused: int = 0
    gates: dict[str, int] = Field(default_factory=dict)
    chain_intact: bool = True
    chain_detail: str = ""


def summarise(log: AuditLog) -> AuditSummary:
    intact, detail = log.verify()
    summary = AuditSummary(
        episode_id=log.episode_id,
        events=len(log.events),
        chain_intact=intact,
        chain_detail=detail,
    )
    for event in log.events:
        if event.verdict is Verdict.ALLOW:
            summary.allow += 1
        elif event.verdict is Verdict.ASK:
            summary.ask_pending += 1
        else:
            summary.block += 1
        if event.ask_text is not None:
            summary.asks_raised += 1
        if event.consent_approved is True:
            summary.asks_approved += 1
        elif event.consent_approved is False:
            summary.asks_refused += 1
        for gate in event.gates_fired:
            summary.gates[gate] = summary.gates.get(gate, 0) + 1
    return summary
